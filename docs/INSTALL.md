# Installation and upgrade

NIRUORG primarily targets Arch/Omarchy and Debian-based desktop distributions, with Python 3 and PySide6.

## Install 0.3.0 from the ZIP

In the directory containing the release archive:

```bash
unzip NIRUORG-0.3.0.zip
cd NIRUORG-0.3.0
chmod +x install.sh
./install.sh
```

On Omarchy, use Kitty/Fish as usual; the above commands are Fish-compatible. Use the Omarchy-supported update procedure (`omarchy update`) if its package policy requires it before package changes. The installer may request sudo for **missing core dependencies**. Optional integrations are no longer installed implicitly on an upgrade.

The installer stores successive releases under `~/.local/share/niruorg/releases/`, verifies the staging installation, and switches `~/.local/share/niruorg/current` only after checks pass. It preserves existing Qt settings and user state. The installed command is `~/.local/bin/niruorg`.

## Optional integrations

The program supports SSHFS/rclone/ffmpeg/mpv and other utilities when available. On an Arch setup these can be installed, as needed, with:

```bash
sudo pacman -S --needed sshfs rclone fuse3 mpv ffmpeg unzip zip
```

Use Debian/Ubuntu equivalents with APT. You do not need all optional integrations just to browse local directories. To explicitly allow the installer to add optional integrations, run `env NIRUORG_INSTALL_OPTIONAL=1 ./install.sh`. This can trigger system package changes; on Omarchy, follow Omarchy’s update policy first.

## Verify active installation

```bash
niruorg --version
readlink -f ~/.local/share/niruorg/current
```

If 0.3.0 is not active, inspect the installer output before retrying. A failed staged upgrade should retain the previous active release.

## Rollback

Before rollback, close NIRUORG and finish/abort active transfers. List available installed releases:

```bash
./rollback.sh --list
```

Then switch to the previous version, for example:

```bash
./rollback.sh 0.2.0
```

The rollback script switches only the active release symlink after checking the target. It does not delete data, connections or newer release directories. Newer settings may not always be understood by older versions; this is why the default 0.3.0 upgrade preserves old settings rather than migrating or rewriting them.

## Uninstall

`./uninstall.sh` removes only application launchers. It intentionally retains local settings, logs, release directories and mounts. Inspect the user's data carefully before manually removing anything.
