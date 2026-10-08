# NIRUORG

**NIRUORG 0.3.0** is a personal, keyboard-friendly two-pane file organizer for Linux, written in Python and PySide6. It is developed primarily for an **Omarchy / Arch Linux + Hyprland + Kitty + Fish** desktop and is also intended to work on Debian-based Linux systems.

This repository publishes the author's *personal setup and development project*, not a commercial file-manager product. It is usable as a standalone app, but your desktop, Qt, FUSE and external integrations may require local configuration.

## What it does

- Two-pane browsing, independent tabs, tab restoration, breadcrumbs and keyboard navigation.
- Local files and folders, Nextcloud sync directories, SSH/SFTP through SSHFS, FTP/FTPS through rclone, plus rclone cloud remotes.
- Drag and drop between local and remote panels (copy by default), with explicit source/destination and transfer activity.
- Copy, move, cancel, transfer conflict decisions and file resume from *verified* partial data.
- Work Basket for collecting file references from different locations; Workspaces and Collections for saved workflows.
- Compare two locations without automatic destructive synchronization.
- Search, Quick Look/preview, image gallery, archives, duplicate finder, checksums, actions and recipes.
- Niru Noir, C. Larsson, Satie, Nord and Follow Omarchy themes.

**Remote-to-remote:** a transfer generally passes through *this computer*. It is not a server-side copy. FUSE can become unavailable or block despite mount-table status; read [Known limitations](#known-limitations) and [Architecture](docs/ARCHITECTURE.md).

## Installation

Download the release ZIP, extract it, then run:

```bash
chmod +x install.sh
./install.sh
```

The installer stages a complete new release under `~/.local/share/niruorg/releases/`, checks syntax, runs regression tests and the Qt smoke test, and **only then switches** the `current` symlink. Previous releases remain on disk. The installer requires `python3` and PySide6 (it can install core dependencies using Arch or APT). Other integrations are optional and not changed by default on upgrade; see [Setup and dependencies](docs/INSTALL.md).

Launch with `niruorg`. There are no system-wide application files or Docker services to start.

To try the source without installing, run `./run.sh` in a desktop session with PySide6 already installed.

**Upgrade from 0.2.0:** use the 0.3.0 `install.sh` directly. The installer retains the previous release and existing `QSettings` preferences, connections, Work Basket and workspaces. It does not reset user data. For rollback guidance, see [INSTALL.md](docs/INSTALL.md).

## Daily workflow

1. Select a folder in the left pane and a destination (local, server or cloud) in the right pane.
2. Drag files across to **copy**, or choose an explicit **Move** operation from Actions.
3. Watch the transfer strip at the bottom. Existing destination names trigger a conflict choice.
4. Use **Work Basket** to collect references to files in different directories without moving their originals.
5. Use **Compare panes** for an overview; any transfer remains an explicit user decision.

Useful shortcuts (actual application bindings):

| Action | Shortcut |
|---|---|
| New tab / close tab | `Ctrl+T` / `Ctrl+W` |
| Reopen closed tab | `Ctrl+Shift+T` |
| Split view | `Ctrl+2` |
| Command palette | `Ctrl+K` |
| Address bar | `Ctrl+L` |
| Terminal in current folder | `Ctrl+Alt+T` |
| Work Basket | `Ctrl+D` |
| Show hidden files | `Ctrl+H` |
| File search | `Ctrl+F` |
| Copy to other pane | `Ctrl+Shift+Right` |
| Compare panes | `Ctrl+Shift+M` |

Use **Keybindings** in the app for the complete list. In Hyprland, `Super+Q` sends a normal close request: NIRUORG handles owned mount cleanup during shutdown. A forced kill cannot run cleanup.

## 0.3.0 highlights

This release prioritizes transfer integrity and GitHub readiness:

- Resume checks **all existing partial bytes** against the current source; an incompatible partial fails safely instead of silently corrupting the destination.
- File replacement is staged and only published after a complete copy. A failed transfer does not delete the original target first.
- Directory transfers stage a separate tree, then publish it. Cancelled transfers do not remove an existing destination directory.
- Copy-into-self and unsupported source types are rejected; symlinks are preserved rather than followed.
- Unsafe automatic Undo is refused for replaced originals and remote transfers, rather than risking deletion or GUI stalls.
- Fixed a malformed Qt media icon drawing call and corrected Keybindings hints for `Ctrl+T` / `Ctrl+Alt+T`.
- Added executable Qt-free transfer-integrity tests, a GitHub Actions workflow, release documentation and repository hygiene.

See [CHANGELOG.md](CHANGELOG.md) for version history and [Release notes](RELEASE_NOTES.md) for the current release.

## Data & privacy

- App releases: `~/.local/share/niruorg/releases/`
- Active release: `~/.local/share/niruorg/current`
- Runtime state/logs: `~/.local/state/niruorg/`
- Preferences and connection definitions: Qt `QSettings` for `NIRU/NIRUORG` (typically under `~/.config/NIRU/`)
- Mountpoints: under NIRUORG's user data directory; only mounts created by NIRUORG are considered owned for automatic unmount.
- Passwords are session-only by default. Optional remembered secrets require Linux Secret Service; SSH agent/keys and rclone hold their own credentials.

Do not commit your actual SSH keys, rclone configuration, settings, crash dumps or transfer logs to this repository.

## Known limitations

NIRUORG is evolving software. Some less frequently used metadata, archive, media and local-tool flows still contain synchronous filesystem work; **a faulty FUSE backend can still stall specific operations**. The app's startup, Work Basket, Compare and conflict preflight have dedicated remote guards, but the entire UI cannot be claimed hang-proof. Resume validates existing partial bytes, but the app is not a transactional database or distributed sync engine. Directory replacement can temporarily preserve a recoverable backup if remote cleanup fails. Use backups for important data and test remote operations with disposable files first.

For issues, provide NIRUORG version, distribution, Qt/PySide6 version, which endpoint was involved and reproduction steps. Do not post connection secrets or unredacted logs.

## Contributing, testing & licensing

- [Engineering review](docs/CODE-REVIEW-0.3.0.md) · [Architecture](docs/ARCHITECTURE.md) · [Testing](docs/TESTING.md) · [GitHub release procedure](docs/GITHUB-PUBLISH.md)
- [Security policy](SECURITY.md) · [Contributing](CONTRIBUTING.md)
- **License:** no redistribution license has been selected yet; publishing source code does not by itself grant reuse rights. The repository owner may add a license later.

Developed as a personal Linux tool by Nicklas Rudolfsson.
