#!/usr/bin/env bash
set -Eeuo pipefail
VERSION="0.6.1"; APP="niruorg"; SRC_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"; BASE="$HOME/.local/share/niruorg"; RELEASES="$BASE/releases"; RELEASE_DIR="$RELEASES/$VERSION"; CURRENT="$BASE/current"; BIN="$HOME/.local/bin"; DESK="$HOME/.local/share/applications"; ICON="$HOME/.local/share/icons/hicolor/scalable/apps"; MIME="$HOME/.local/share/mime"; STATE="$HOME/.local/state/niruorg"
echo "NIRUORG $VERSION installer"; echo "------------------------"
# Without a terminal nobody can answer a package manager prompt. --yes,
# NIRUORG_ASSUME_YES=1 or NIRUX_ASSUME_YES=1 (set by `nirux extras install`
# when it runs unattended) is the consent to install missing packages.
ASSUME_YES=0; [[ "${NIRUORG_ASSUME_YES:-${NIRUX_ASSUME_YES:-0}}" == 1 ]] && ASSUME_YES=1
for arg in "$@"; do case "$arg" in -y|--yes) ASSUME_YES=1 ;; -h|--help) echo "usage: ./install.sh [--yes]"; exit 0 ;; *) echo "unknown option: $arg" >&2; exit 2 ;; esac; done
YES_PACMAN=(); YES_XBPS=(); [[ $ASSUME_YES == 1 ]] && { YES_PACMAN=(--noconfirm); YES_XBPS=(-y); }
if [[ ! -t 0 && $ASSUME_YES != 1 ]]; then NO_TTY_NOTE='(no terminal: run in a terminal or with --yes if this fails)'; else NO_TTY_NOTE=''; fi
need(){ python3 - <<'PY' >/dev/null 2>&1
import PySide6
PY
}
if ! command -v python3 >/dev/null || ! need; then
 echo "Installing core dependencies... $NO_TTY_NOTE"
 if command -v pacman >/dev/null; then sudo pacman -S --needed "${YES_PACMAN[@]}" python pyside6
 elif command -v xbps-install >/dev/null; then sudo xbps-install -S "${YES_XBPS[@]}" python3 python3-pyside6 python3-pyside6-gui python3-pyside6-widgets
 elif command -v apt-get >/dev/null; then sudo apt-get update; sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets
 else echo "Unsupported package manager. Install Python 3 + PySide6." >&2; exit 1; fi
 need || { echo "ERROR: PySide6 cannot be imported after installing the dependencies." >&2; exit 1; }
fi
# Opt-in for optional tools: upgrades must not unexpectedly change packages.
if [[ "${NIRUORG_INSTALL_OPTIONAL:-0}" == '1' ]]; then
 echo "Installing optional integrations at user request..."
 if command -v pacman >/dev/null; then sudo pacman -S --needed "${YES_PACMAN[@]}" mpv fd ripgrep p7zip unzip zip libarchive sshfs libsecret ffmpeg rclone fuse3
 elif command -v xbps-install >/dev/null; then sudo xbps-install -S "${YES_XBPS[@]}" mpv fd ripgrep 7zip unzip zip bsdtar fuse-sshfs libsecret ffmpeg rclone fuse3
 elif command -v apt-get >/dev/null; then sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y mpv fd-find ripgrep p7zip-full unzip zip libarchive-tools sshfs libsecret-tools ffmpeg rclone fuse3; fi
else
 echo 'Optional integrations are not modified on upgrade (set NIRUORG_INSTALL_OPTIONAL=1 to opt in).'
fi
mkdir -p "$RELEASES" "$BIN" "$DESK" "$ICON" "$MIME/packages" "$STATE"; STAGE="$RELEASE_DIR.staging"; trap 'rm -rf "$STAGE"' ERR INT TERM; rm -rf "$STAGE"; mkdir -p "$STAGE"; cp -a "$SRC_DIR"/. "$STAGE"/
python3 -m py_compile "$STAGE/niruorg/app.py" "$STAGE/regression-suite.py" $(find "$STAGE/tests" -maxdepth 1 -type f -name '*-test.py' -print)
python3 "$STAGE/regression-suite.py"
python3 "$STAGE/niruorg/app.py" --self-test
QT_QPA_PLATFORM=offscreen timeout 8s python3 "$STAGE/tests/gui-smoke-test.py"
find "$STAGE" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true; find "$STAGE" -type f -name "*.py[co]" -delete 2>/dev/null || true
PREV=""; [ -L "$CURRENT" ] && PREV="$(readlink -f "$CURRENT" || true)"
if [[ "$PREV" == "$RELEASE_DIR" ]]; then
 # The active release is never replaced in place. Its launcher, desktop entry
 # and icon are rewritten below, so a reinstall after ./uninstall.sh (which
 # keeps the release directories) works instead of refusing.
 echo 'This release is already active; keeping its files and restoring the launcher.'
 rm -rf "$STAGE"
else
 rm -rf "$RELEASE_DIR"; mv "$STAGE" "$RELEASE_DIR"; ln -sfn "$RELEASE_DIR" "$CURRENT.new"; mv -Tf "$CURRENT.new" "$CURRENT"
fi
cat > "$BIN/niruorg" <<'EOF'
#!/usr/bin/env bash
APP_HOME="$HOME/.local/share/niruorg/current"; STATE="$HOME/.local/state/niruorg"; mkdir -p "$STATE"; exec python3 "$APP_HOME/niruorg/app.py" "$@" 2>>"$STATE/launcher.log"
EOF
chmod +x "$BIN/niruorg"; sed -e "s|^Exec=.*|Exec=$BIN/niruorg %F|" -e "s|^TryExec=.*|TryExec=$BIN/niruorg|" "$RELEASE_DIR/niruorg.desktop" > "$DESK/niruorg.desktop"; cp "$RELEASE_DIR/assets/niruorg.svg" "$ICON/niruorg.svg"; cp "$RELEASE_DIR/mime/nirupres.xml" "$MIME/packages/nirupres.xml"; command -v update-mime-database >/dev/null && update-mime-database "$MIME" >/dev/null 2>&1 || true; command -v update-desktop-database >/dev/null && update-desktop-database "$DESK" >/dev/null 2>&1 || true
"$BIN/niruorg" --version >/dev/null || {
 echo "Installed entrypoint failed; restoring previous version." >&2
 if [[ -n "$PREV" ]]; then ln -s "$PREV" "$CURRENT.restore.$$"; mv -Tf "$CURRENT.restore.$$" "$CURRENT"; fi
 exit 1
}
trap - ERR INT TERM; echo; echo "NIRUORG $VERSION installed successfully."; echo "Launch: niruorg"; echo "Log: $STATE/launcher.log"
