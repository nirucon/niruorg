## 0.4.0 — 2026-10-08

- Keyboard-first searchable command palette replaces the old Actions picker.
- New palette regression contract and version alignment.
- Maintains 0.3.0 transfer safety and upgrade architecture.
- Known limitations and future features explicitly documented.

# Changelog

## 0.3.0 — Transfer Integrity & GitHub Baseline

- Verified existing `.niruorg-part` bytes against the current source before allowing resume; mismatched partials are refused and preserved.
- Replaced delete-first file overwrites with fully staged atomic publication; staged directory replacement keeps its previous contents until new files are ready, with rollback if promotion fails.
- Rejected recursive self-copy, preserved symlinks, and prevented cancelled directory transfers from deleting existing destinations.
- Made Undo conservative for replaced originals and remote endpoints.
- Fixed a malformed media icon polygon call, corrected published keyboard shortcuts, and removed personal server names from connection hints.
- Secured the temporary SSH askpass helper with a unique pathname and restrictive file creation.
- Made optional package installation opt-in, protected active releases against in-place replacement and added a rollback helper.
- Added executable Qt-free transfer-integrity tests, GitHub Actions, English documentation, engineering review and security/contributing guidance.

## 0.2.0 — Reliability & Workflow

- Remote/FUSE metadata checks are moved away from the GUI thread for Work Basket, Compare Workspace and transfer conflict discovery.
- Work Basket is endpoint-aware and distinguishes Available, Offline, Missing and Unavailable without synchronously dereferencing stale remote mounts.
- Compare Workspace now performs metadata discovery asynchronously with bounded remote subprocess timeouts and remains explicit/non-destructive.
- Transfer destination conflict discovery is asynchronous, so stale SSHFS/rclone destinations cannot freeze the GUI before a transfer starts.
- Local-only free-space preflight remains synchronous; remote capacity checks are deliberately not performed on the GUI thread.
- Sidebar drag acceptance no longer calls Path.is_dir() during a Wayland drag operation.
- Remote-to-remote transfers remain explicit client-mediated copies through this computer; no server-side sync semantics are implied.
- Preserves 0.1.10 transfer activity, 0.1.9 Wayland DnD, 0.1.7 Qt worker lifetime safety and 0.1.6 FUSE ownership/unmount lifecycle.
- README and release metadata are consolidated around the current 0.2.0 milestone.

## 0.1.10 — Transfer activity

- Added a compact, persistent transfer activity strip for Copy/Move/DnD/Work Basket transfers.
- Shows source → destination, current item, byte progress, throughput and ETA for file transfers.
- Multiple concurrent transfers are represented without modal progress dialogs.
- Added safe Cancel for the visible transfer; partial files remain resumable according to the existing transfer engine.
- Closing NIRUORG with active transfers now offers safe cancellation and waits for workers to finish before remote unmount/exit.
- Preserves 0.1.9 Wayland cross-endpoint DnD, 0.1.7 worker lifetime safety and 0.1.6 FUSE lifecycle fixes.

## 0.1.9
- Fixed Wayland cross-pane drag-and-drop: the native drop event now completes before NIRUORG starts transfer UI, preventing an unresponsive modal dialog after dropping onto a remote pane.
- Copy by drag-and-drop no longer asks for redundant confirmation; copy is non-destructive and name conflicts remain explicitly handled.
- Confirmation dialogs now give the affirmative action proper default focus for keyboard operation.

# Changelog

## 0.1.7 — Qt worker lifetime stability

- Fixed a reproducible startup SIGSEGV in PySide6/Qt caused by short-lived `QRunnable` Python wrappers owning `QObject` signal objects while queued GUI callbacks were still pending.
- External discovery is now a module-level worker and all NIRUORG QRunnables started by `Main` are retained explicitly until a terminal signal has been delivered and the GUI event queue advances.
- Remote startup/probe workers are drained with a bounded wait during shutdown before FUSE models are detached and NIRUORG-owned mounts are unmounted.
- Preserves the 0.1.6 FUSE ownership, stale-mount protection and safe unmount lifecycle.

## 0.1.6 — FUSE mount lifecycle safety

- NIRUORG now tracks ownership of SSHFS/rclone mounts it creates and only auto-unmounts those owned mounts.
- Normal window close, including Hyprland/Omarchy Super+Q close requests, detaches remote QFileSystemModel roots before unmounting.
- Shutdown uses bounded normal FUSE unmount first and a bounded lazy fallback, so a stale remote cannot indefinitely block exit.
- Mount ownership is journaled atomically under `~/.local/state/niruorg/owned-mounts.json`; external mounts are never claimed merely because they exist.
- Replaced remote `os.path.ismount()` checks with `/proc/self/mountinfo` metadata checks so status/UI code does not stat a stale FUSE mount.
- Server and cloud disconnects release ownership after successful unmount; successful connections are claimed only after mountinfo confirms the mount.
- Preserves the 0.1.5 non-blocking startup architecture and remote probe boundaries.

## 0.1.5 — Non-blocking startup and remote I/O

- Reworked startup so the main window is built from cheap local state and shown before session restore, rclone discovery or remote probing.
- Removed synchronous saved-path `exists`/`is_dir` checks, `/mnt` traversal and FUSE `resolve` calls from sidebar/session startup.
- Server mount status now comes from `/proc/self/mountinfo`, which does not touch the FUSE backend.
- rclone discovery runs after the window is shown in a bounded two-worker pool.
- Remote/FUSE navigation and restored remote tabs use an asynchronous, timeout-bounded probe and show `Checking…`, `Offline` or `Unavailable` instead of freezing startup.
- Remote probe results are generation-tokened so stale results cannot overwrite newer navigation.
- QFileSystemModel no longer receives a root path during pane construction; local Home is attached only after the main UI exists.
- Double-click navigation uses QFileSystemModel metadata instead of an extra synchronous `Path.is_dir()` call.
- Added lightweight startup timing at `~/.local/state/niruorg/startup.log`.
- Added startup/FUSE regression coverage while preserving panes, tabs, connections, mounts, pins, bookmarks and session state.

## 0.1.4 — Pane & tab state consistency

- Closing the final tab in the optional right pane now closes split view; the primary left pane always retains a usable Home tab.
- Hiding the right pane is distinct from closing its tabs: Ctrl+2 can restore the hidden right workspace during the session.
- Reopen Closed Tab remembers the originating pane and can recreate the right pane with its previous tab state.
- Moving the last tab out of either pane preserves the left-pane invariant and closes an exhausted right pane cleanly.
- Per-tab filter state is preserved together with path, navigation history, remote identity and pin state.
- Double-clicking empty tab-bar space opens a new tab; pinned tabs remain protected from ordinary close actions.
- Closing NIRUORG while file transfers are active now warns before interrupting them.
- Session/workspace restoration tolerates an optional right pane and keeps active-pane semantics consistent.
- Fixed a latent Shortcuts dialog callback referencing a non-existent import button.
- No new color accents; active pane, selected tab and selected file remain a monochrome hierarchy.

## 0.1.4 — Noir UI polish

- Removed the accidental horizontal scrollbar from the fixed-width sidebar; long entries now elide instead of creating the bottom rectangle.
- Replaced platform-colored tab close controls with NIRUORG-owned monochrome close buttons.
- Active pane, active tab and transfer progress use neutral foreground/border tones rather than theme accent colors.
- Smarter tab labels: the local home directory is `Home`; remote tabs include connection context such as `remote · Home`. Full logical paths remain in tooltips.
- Preserved per-pane tabs, split view, FileZilla import, connections and all 0.1.1 workflows.

## 0.1.1 — Pane workflow & reliability

- Added multiple tabs independently in each pane, with clear active-pane versus active-tab hierarchy.
- Added Ctrl+T new tab and Ctrl+W close tab; terminal moved to Ctrl+Alt+T.
- Interrupted file transfers retain safe `.niruorg-part` data and can resume on retry.
- Added direct-file free-space preflight before transfers.
- Remote Open Terminal Here now opens SSH directly in the logical remote directory.
- Locations terminology replaces Targets in navigation while retaining compatible stored data.
- Package Inspector now checks single root, package/root naming and common release files.
- Preserved and integrated Connection Manager/FileZilla import, Workspaces, Compare Panes, Quick Actions, Quick Look, batch rename, duplicate finder, Git/project context, diagnostics and transfer history.
- Fixed a latent Locations/Targets dialog callback referencing a non-existent Import button.


## 0.1.0
- Major usability and connection-management milestone based on the stable 0.0.55 two-pane architecture.
- FileZilla `sitemanager.xml` import with per-site selection and optional password migration to Linux Secret Service; passwords are never written to NIRUORG settings.
- OpenSSH config import for host, user, port, identity file and ProxyJump.
- Proton Pass CLI detection as a completely optional integration; no Proton dependency is introduced.
- Connection Manager now exposes Import directly.
- Package Inspector validates ZIP/TAR packages, reports root structure, sizes and SHA-256.
- Safe System Diagnostics report for support without passwords, tokens or private-key contents.
- Retains Workspaces, Locations/targets, Quick Actions, Quick Look, Compare Panes, transfer queue/history, safe partial-copy, conflict policies, checksums, archives, cloud/rclone and SSH/SFTP/FTP/FTPS support.
- Existing NIRUORG settings and connection definitions remain compatible.


## 0.1.0
- Made the active pane explicit with a compact marker in each pane identity and synchronized focus styling.
- Sidebar context menus now say exactly where the alternate action goes: Open in left pane / Open in right pane.
- Cross-pane file actions now say Copy/Move to left/right pane instead of the ambiguous “other pane”.
- Actions menu labels update immediately when focus changes between panes.
- Split status line identifies Left active / Right active, while drag-and-drop remains direct source → destination.
- Preserves 0.0.54 release-harness hardening and 0.0.53 remote/split correctness fixes.


## 0.1.0
- Corrected the 0.0.53 release packaging: archives again contain the expected top-level NIRUORG-version directory.
- Fixed the regression manifest so every TESTS entry uses the required (name, qt, timeout) tuple schema.
- Added a regression-manifest schema test so malformed entries are rejected before release packaging.
- Preserves the 0.0.53 splitter, remote identity, logical remote breadcrumb and transfer improvements.


## 0.0.53
- Reliable draggable Split View divider with a 7 px interaction target and minimal visual line.
- Split proportions are remembered/restored; safe 50/50 default.
- Verified SSHFS/cloud mount paths recover REMOTE identity automatically.
- Remote breadcrumbs show logical server paths, not internal mount paths.
- Stronger active-pane focus refresh while preserving local ↔ remote ↔ remote drag/drop and transfers.


## 0.0.52
- Fixed remote file panes falling back to the local filesystem root when QFileSystemModel had not loaded an SSHFS path yet.
- Remote panes now fail closed at their verified mount root instead of silently becoming local panes.
- Added explicit panel identity: `LOCAL · hostname` and `REMOTE · server · protocol`.
- Split View now preserves remote identity when duplicating a remote pane and remains compatible with local↔server and server↔server transfers.
- Added regression coverage for asynchronous QFileSystemModel roots and remote mount confinement.

## 0.0.52
- Fixed the async SSHFS completion bug that could mount a server successfully but leave the target file pane on the local machine.
- Remote pane binding now resolves the saved connection explicitly by name after mount completion instead of referencing an out-of-scope connection variable.
- Added post-bind verification: a successful remote mount must actually place the target pane inside that remote mount or NIRUORG reports an error instead of silently showing local files.
- Preserves the SSHFS-backed transfer architecture for local ↔ server and server ↔ server transfers in Split View.
- Added a regression test for the exact async remote-pane binding failure fixed in this release.

## 0.0.52
- Fixed remote connections opening in the wrong split pane by binding each asynchronous connection to the pane that requested it.
- Remote panes now show an explicit `server · protocol` identity and the remote path instead of exposing the local SSHFS mount path.
- Existing filesystem transfer engine is now explicitly exercised for local ↔ server and server ↔ server split workflows.
- Added regression coverage for remote pane binding, remote identity and cross-endpoint split transfers.

## 0.0.48
- Replaced the external terminal-based `ssh-add` unlock flow with a native NIRUORG passphrase dialog.
- Passphrases are masked and remain ephemeral: they are not persisted in settings/logs, command arguments, environment variables, or files.
- OpenSSH still performs key loading; NIRUORG supplies the passphrase through a short-lived inherited pipe to an `SSH_ASKPASS` helper and removes the helper immediately afterward.
- Preserves the verified 0.0.47 SSH-agent startup/reuse behavior and automatic retry after a successful unlock.

- Fixed SSH agent startup/unlock regression: `re.search()` was used to parse `ssh-agent` output without importing Python's `re` module.
- Added a regression test that verifies the parser dependency is imported and the agent environment parser remains present.
- Preserves 0.0.46 remote/SFTP behavior, including existing-agent reuse and interactive `ssh-add` key unlock.

# 0.0.46

- Fixed SSH key unlock on systems where a freshly started ssh-agent is valid but `ssh-add -l` cannot be used as an immediate startup gate.
- NIRUORG now trusts the `SSH_AUTH_SOCK` and `SSH_AGENT_PID` emitted by OpenSSH and lets interactive `ssh-add` plus the SSH preflight perform the real authentication verification.
- Keeps OpenSSH/Auto, explicit SSH key, password, SFTP/SSH, FTP/FTPS and Tailscale connection modes separate.

# NIRUORG 0.0.46

- Fixes SSH-agent startup on Arch/Omarchy and Debian/Ubuntu by parsing the environment returned by OpenSSH instead of assuming a socket path.
- Validates a newly started agent with `ssh-add -l` before using it.
- Falls back to OpenSSH's native agent socket when an explicit `-a` socket cannot be used.
- Keeps existing desktop agents preferred and keeps private NIRUORG agents session-scoped.
- Adds regression coverage for portable SSH-agent startup.

# NIRUORG changelog

## 0.0.46
- Reworked SSH key unlock for Arch/Omarchy and Debian/Ubuntu.
- Reuses a working inherited ssh-agent; otherwise starts a private NIRUORG-session ssh-agent.
- Passphrase entry stays inside OpenSSH ssh-add; NIRUORG never stores it.
- Unlock is detected automatically and the original connection resumes without manual Retry.
- SSH/SSHFS processes inherit the selected agent environment.
- Private agent is cleaned up when NIRUORG exits.
- Fixed literal HTML markup in the unlock dialog.

# Changelog

## 0.0.46
- Connections: added read-only staged diagnostics for DNS/host resolution, Tailscale reachability, TCP port and SSH authentication.
- Diagnostics distinguish network/port failures from SSH key/authentication failures, based on remote connection troubleshooting.
- Connection diagnostics run in the Qt thread pool so slow network checks do not freeze the Connections UI.
- Fixed installer regression: 0.0.41 interaction regression is now executed as its own command instead of accidentally being passed as an argument to the 0.0.39 test.
- Added a regression guard for the installer test chain.


## Gallery / Focus Viewer
- Fixed the modal-parent bug that made fullscreen controls unresponsive when Focus was opened from Gallery.
- Focus Viewer is now owned by the Gallery dialog, so mouse and keyboard input remain active under Qt/Wayland.
- Fit uses the actual image viewport and recalculates on resize/fullscreen changes.
- Esc exits fullscreen first, then returns to Gallery; F11 toggles fullscreen.
- Previous/Next, Fit/100%, Home/End, arrows, Space and Backspace remain available.

## NIRU Player
- Refined the compact player hierarchy and timeline while keeping MPV as the playback backend.
- Added clearer queue position, elapsed/duration display and keyboard hinting.
- Fixed Stop/track-change races so manually stopping or changing track does not accidentally trigger auto-next.

## Remote servers
- Added **Unlock SSH key…** for encrypted OpenSSH keys. It runs `ssh-add` in the configured terminal and keeps the passphrase out of NIRUORG.
- SFTP/SSH continues to use OpenSSH/ssh-agent/SSHFS; no duplicate private-key storage is introduced.
- Connection failures involving public-key/passphrase authentication now point to the unlock workflow.
- SFTP/SSH over Tailscale supports MagicDNS names.

# NIRUORG 0.0.41

- Fixes the Connections GUI regression test itself: the old test synchronously clicked a button whose handler enters QDialog.exec(), so its polling callback could not observe the nested editor reliably.
- The new test schedules verification inside the nested Qt event loop, confirms Add connection is visible and owned by Connections, then closes it cleanly.
- Installer keeps the GUI gate, but it is now deterministic and bounded by timeout.
- No credentials, server definitions or user data are migrated or rewritten.

# NIRUORG 0.0.41 — Connection activation fix

- Corrected the real Qt regression test: the Add connection editor is a parented child QDialog of Connections and is therefore discovered through the manager widget tree, not assumed to be an independent top-level widget.
- Keeps the Wayland-safe 0.0.38 connection editor ownership (Connections is the parent; no raise()/activateWindow()).
- Installer still refuses activation on a real Add connection failure, but no longer rejects a working child dialog because of incorrect test discovery.

# NIRUORG 0.0.41

- Fixed Connections → Add connection with guarded editor launch and safe dynamic form visibility.
- Added a real Qt click-through regression test for the Add connection button.
- Gallery Focus: fullscreen image review with keyboard navigation; Escape returns to Gallery.
- Gallery UX: Focus/Close controls, larger progressive thumbnails, Enter/F11 opens Focus.
- NIRU Player 1.0: compact themed audio player using MPV as playback backend, with play/pause, previous/next, seek and progress.
- Audio playback preference: NIRU Player, system default, MPV, VLC or cmus.
- Preserves neutral theme-driven controls; no colored media/status icons.
- Fixed installer regression where dialog-connection test was accidentally passed as an argument instead of executed.

# 0.0.41 — Dialog & Connection Reliability

- Fixes Add connection/Edit connection failing before the editor opened due to invalid Qt item-role arithmetic.
- Connection Manager now has a dedicated Close button; network-operation cancellation is clearly labelled Cancel operation.
- Connection actions are disabled until a connection is selected and update with protocol/context.
- Introduces NiruDialog for consistent Escape-to-close behavior and an automatic neutral Close button on ordinary popup dialogs that otherwise have no obvious exit.
- Keeps dialog controls theme-neutral; no colored status icons are introduced.
- Adds regression coverage for connection-button wiring, dialog exit behavior, and the original Add connection crash.


## 0.0.41 — Remote UX & Diagnostics
- Reworked Connections UI for clearer everyday server use.
- Context-sensitive connection editor: irrelevant SSH/FTP/TLS/password controls are hidden.
- OpenSSH / Auto is the recommended SSH mode for ssh-agent, ~/.ssh/config and standard keys.
- Explicit SSH key mode now requires an actual identity file selection.
- Added Save & connect flow.
- Cleaner connection list, tooltips and neutral structured Connection Details.
- Tailscale guidance clarified for MagicDNS, 100.x addresses and Tailscale SSH.
- Theme-neutral information/error/confirmation dialogs; no colored QMessageBox status icons in normal workflows.
- Preserves existing 0.0.32 connection data and secure Secret Service behavior.

# NIRUORG 0.0.41

## Sidebar Connections UX
- Server entries are now destinations: click a disconnected server to connect, click a connected server to open it.
- Direct connect asks only for missing credentials; successful sidebar connection opens the remote location and closes the connection dialog.
- Right-click server menu: Connect/Open, Open in other pane, SSH terminal when applicable, Details, Test, Disconnect, Edit, Duplicate and Remove.
- Server tooltips expose protocol, route (including Tailscale), endpoint and connection state.
- SERVERS is always visible and includes Add connection.
- Double-click in Connections now connects/browses instead of unexpectedly editing.
- Existing 0.0.31 server definitions remain compatible.

# NIRUORG 0.0.41

## Remote Connections
- Reworked Server Manager into a clearer Remote Connections workflow for SFTP/SSH, FTP and FTPS.
- Added Tailscale-aware setup: direct/LAN/Internet, Tailnet via MagicDNS or 100.x address, and Tailscale SSH terminal mode.
- Added explicit and implicit FTPS modes, passive FTP and TLS certificate verification controls.
- Added SSH ProxyJump and configurable keepalive in Advanced settings.
- Added connection Details with protocol, route, mount state and dependency/capability overview.
- SFTP is presented as the recommended remote file protocol; SSH terminal access is a separate action on the same connection.
- Existing 0.0.30 server definitions remain compatible; new fields use safe defaults.
- Passwords remain absent from NIRUORG settings and command-line arguments; Secret Service remains optional for remembered credentials.

# NIRUORG 0.0.30

## Stability & Workflow
- File Safety 1.0 hardens ZIP/TAR extraction against path traversal and archive links that can escape the destination.
- Directory transfers now preserve directory symlinks as symlinks without traversing their targets.
- Work Basket 4.1 accepts drag-and-drop files/folders, marks missing items, removes stale entries, and reveals items by double click.
- Workspace Snapshots 1.1 adds rename, duplicate and explicit removal confirmation.
- Path Actions now support opening a breadcrumb folder in the other pane and adding it directly to Work Basket.
- Existing Search 3.0, Compare Workspace 2.0, Server Manager and persistent settings remain compatible.

# NIRUORG 0.0.29

- Work Basket replaces the session-only Drop Zone as a persistent cross-folder working set.
- Intent Actions (Ctrl+K) ranks built-in and user-defined NIRU Actions from the current selection and detected capabilities.
- Workspace Snapshots now restore split state, active pane and Quick Look in addition to locations.
- Context Lens 2.0 adds richer local project/folder/media context without synchronous external commands, network calls or indexing.
- Search results add directly to the persistent Work Basket.
- Preserves 0.0.28 Search 3.0, Compare Workspace 2.0, server/password architecture and safe transfer engine.

## Previous 0.0.28

## Search 3.0 / Compare Workspace
- Search now uses the existing background SearchWorker instead of blocking the Qt event loop. Results stream into the view and searches can be cancelled.
- Search results support multi-selection and can be staged directly in Drop Zone.
- Compare panes is now an actionable Compare Workspace with explicit Send and Receive operations; no automatic synchronization.
- Integration capability detection now includes NIRUNOTE, NIRUPRES and NIRUWORD.
- File safety and existing server/cloud/delete behavior are preserved from 0.0.27.

- Expanded Server Manager to SSH/SFTP, FTP and FTPS with explicit protocol and authentication settings.
- Added OpenSSH/Auto, explicit SSH key and password authentication modes.
- Passwords are never written to NIRUORG server configuration or command-line arguments.
- Optional remembered passwords use Linux Secret Service through secret-tool; otherwise passwords live only for the current NIRUORG session.
- Password-based SFTP/FTP/FTPS uses an ephemeral mode-0600 rclone configuration that is removed after the operation starts/finishes.
- Test and Connect remain asynchronous, cancellable and time-limited; failed network operations do not block the Qt GUI.
- Interactive SSH opens a terminal and lets OpenSSH handle password prompts directly.
- Server editor now supports protocol, authentication method, identity file, remote path and per-server timeout.

# NIRUORG 0.0.26

- Rebuilt Server Manager with asynchronous QProcess network operations; SSH/SFTP tests and mounts no longer block the Qt GUI.
- Add, edit, clone and remove server profiles.
- Test connections without mounting, with BatchMode and configurable timeout.
- Connect/disconnect with timeout, cancel and forced cleanup fallback.
- Support SSH agent/default OpenSSH configuration, optional identity file, custom port, remote path and host aliases.
- Clear per-operation status and safe removal rules for mounted servers.
- Added server-manager regression contract to staged installation.

- Split View UX: both panes retain independent breadcrumbs, Back/Parent navigation and filters; the secondary pane has an explicit close control and Ctrl+2 reliably returns to single-pane view without changing the primary path.
- Sidebar section headers have clearer expand/collapse affordance, larger full-row hit areas through the existing list interaction, hover/focus feedback, bold labels and persisted collapsed state. SHORTCUTS and CLOUD remain visible even when empty.
- Cloud Manager based on rclone for Google Drive, OneDrive personal, Microsoft 365 work/school and other rclone providers such as Dropbox, WebDAV, S3 and Box.
- Cloud remotes are mounted only on demand under ~/.local/share/niruorg/cloud; NIRUORG does not implement a sync daemon and does not store Google/Microsoft passwords.
- Existing local Nextcloud integration remains available under the same CLOUD section.
- Mounted cloud remotes can be opened/unmounted from Cloud Manager or the sidebar context menu.
- Fixed stale legacy CLOUD insertion code in Pin current folder.

# NIRUORG 0.0.24

- Linux/XDG file associations for NIRUPRES and NIRUNOTE with capability detection.
- Open With and NIRU application discovery.
- Context Lens for Git, Python, Node, Docker and media folders.
- Session restore for folders and split view.
- Markdown Quick Create opens through the preferred association.
- Search groundwork remains non-indexed and existing safe transfer/delete architecture is preserved.
- Expanded release regression contract.

# NIRUORG 0.0.24

## Workflow release

- NIRU Actions: reusable, selection-aware commands configured in the GUI.
- Safe argv execution: actions never use `shell=True`; placeholders expand as arguments.
- Recipes: named chains of NIRU Actions with a confirmation preview before execution.
- Actions and Recipes are available from the Actions menu, Ctrl+K, file context menus and Drop Zone.
- Drop Zone can now copy or move staged items to the active folder and run Actions/Recipes.
- Safer file copies: regular files are written as `.niruorg-part`, flushed, and atomically published with `os.replace()` only after a successful copy. Cancel/failure removes the partial file.
- Existing permanent-delete BrowserTree path and confirmation model are retained.
- Added workflow regression coverage and release hygiene checks.
- No daemon, filesystem indexer or background scanner added.

# NIRUORG 0.0.24

## Keyboard reliability
- Replaced application-event-filter execution of browser keys with view-owned `QShortcut` bindings.
- `Shift+Delete`, `Delete`, F2, F5, Backspace, Return/Enter and Space now belong directly to each file pane.
- This avoids QAction/ShortcutOverride races and uses the same Qt mechanism on Wayland/Hyprland and X11/DWM.
- Shortcut regression now verifies direct pane bindings and actual dispatch to permanent delete vs Trash.
- Input diagnostics now records the final `dispatch` action when enabled.
- Context menu keeps `Move to Trash` and `Delete Permanently…`; both use the same final file-operation methods as keyboard actions.

# NIRUORG 0.0.24

- Added opt-in Help → Input diagnostics for Qt/Wayland shortcut troubleshooting. It records only event type, numeric key/modifier flags, target widget and pane; never typed text.
- Added `Delete Permanently…` directly beside `Move to Trash` in the file context menu for files and folders.
- Context-menu permanent deletion and Shift+Delete use the same `permanent_delete()` implementation.
- Kept diagnostics off by default with no idle overhead.

# NIRUORG 0.0.24

- Fixes startup regression in 0.0.17: early Qt events are now safe before file panes exist.
- Browser focus/event resolution is defensive throughout Main initialization.
- Shortcut regression test explicitly covers constructing Main from a cold start.
- Keeps the deterministic browser shortcut routing introduced for Shift+Delete.

# NIRUORG 0.0.24

- Fixed browser-level keyboard routing, especially `Shift+Delete`.
- Shortcut routing now uses the actual Qt event target/viewport rather than relying on active-window/focus assumptions.
- Added a single `_dispatch_browser_key()` path used by runtime and regression tests.
- Strengthened shortcut regression coverage for Delete, Shift+Delete, F2, F5, Backspace, Return and Space.
- Failed staging releases still never replace the active release.

# NIRUORG 0.0.24

- Robust browser-level standard key handling, including Shift+Delete permanent delete.
- Safe Rename selects basename by default and rejects collisions.
- Archive Browser with filtering and safe selected extraction.
- Temporary Split for fast one-off two-pane workflows.
- Breadcrumb Path Actions context menu.
- Keyboard/release regression checks strengthened.

# NIRUORG 0.0.24

- Saved Searches: reusable on-demand file/content queries without indexing.
- Folder Health: fast non-recursive diagnostics for broken symlinks, empty/unreadable folders and large files.
- Duplicate Finder: explicit recursive scan with SHA-256 verification, cancel support and no automatic deletion.
- Clipboard Inspector with Ctrl+Shift+V.
- Search can save the current query from the Find UI.
- Added the new tools to menus, Command Palette, Help/Keybindings and release self-tests.
- Preserves staged fail-safe upgrades and resource-light idle behavior.

# NIRUORG 0.0.24

- Help → Keybindings: searchable, grouped shortcut reference generated from the application shortcut model.
- About: new product description and creator credit.
- Standard file-manager bindings expanded: Shift+Delete, Alt+Left/Right, F5, Ctrl+A, Ctrl+N, Escape.
- Quick Create for text, Markdown and folders.
- Neutral action-button UX retained; no decorative red/green action icons.
- Refresh and forward navigation added.
- Command Palette exposes New and Keybindings.

# NIRUORG 0.0.24

- Settings UX: `Date & time`, clearer permanent-delete checkbox, neutral action buttons, live theme/density preview with Cancel rollback.
- Search 2.0 (`Ctrl+F`): dedicated Find UI, current-folder/Home scope, filename search via fd/fdfind, optional content search via ripgrep, hidden-file option, result list, open and open-containing-folder.
- Jump (`Ctrl+P`): instant navigation across Places, user Shortcuts, recent locations and Workspaces without disk indexing.
- Focus Browser (`F10`): hides sidebar/menu/status for a minimal file-only workspace.
- Recent Locations: lightweight navigation history persisted without file indexing.
- Transfer Engine 2.0: recursive directory copies now use the chunked/cancellable transfer path rather than blocking copytree; partial cancelled directory destinations are cleaned up.
- MPV shortcut moved to `Ctrl+Shift+P` to reserve `Ctrl+P` for Jump.
- Existing Quick Look, Gallery, Split View, SFTP/SSH, Nextcloud, Drop Zone, Collections, Targets, Workspaces, Compare, Operations, semantic icons and Omarchy theming retained.
- Release/smoke contracts extended for the new navigation/search features.

## 0.0.41 — Interaction Reliability & Media UX
- Reworked Connections Add flow: editor is now an application-modal transient of the main window, explicitly surfaced/focused, with visible status and error reporting.
- Added 0.0.41 interaction regression coverage; installer still runs the real PySide6 click-through test before activation.
- Gallery Focus now has visible Previous/Next/Fit/Fullscreen/Close controls plus keyboard hints; F11 toggles fullscreen and Esc first exits fullscreen, then closes focus.
- Gallery adds explicit Focus/Fullscreen and Slideshow controls.
- Audio files now open through the configured audio player; context menu exposes Play in NIRU Player and configured-player actions only when relevant.
- NIRU Player remains MPV-backed; no custom codec/audio engine added.

### 0.0.48 packaging correction
- Replaced brittle SSH unlock regression assertion on exact UI copy with behavioural/security invariants.
- Added one authoritative regression-suite manifest; installer no longer maintains duplicate compile/run test lists.
- Installer refuses activation if a regression test exists but is not registered, preventing new tests from being silently skipped.
