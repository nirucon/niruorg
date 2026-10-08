#!/usr/bin/env bash
set -Eeuo pipefail
VERSION="0.3.0"; APP="niruorg"; SRC_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"; BASE="$HOME/.local/share/niruorg"; RELEASES="$BASE/releases"; RELEASE_DIR="$RELEASES/$VERSION"; CURRENT="$BASE/current"; BIN="$HOME/.local/bin"; DESK="$HOME/.local/share/applications"; ICON="$HOME/.local/share/icons/hicolor/scalable/apps"; MIME="$HOME/.local/share/mime"; STATE="$HOME/.local/state/niruorg"
echo "NIRUORG $VERSION installer"; echo "------------------------"
need(){ python3 - <<'PY' >/dev/null 2>&1
import PySide6
PY
}
if ! command -v python3 >/dev/null || ! need; then
 echo "Installing core dependencies..."
 if command -v pacman >/dev/null; then sudo pacman -S --needed python pyside6
 elif command -v apt-get >/dev/null; then sudo apt-get update; sudo apt-get install -y python3 python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets
 else echo "Unsupported package manager. Install Python 3 + PySide6." >&2; exit 1; fi
fi
# Opt-in for optional tools: upgrades must not unexpectedly change packages.
if [[ "${NIRUORG_INSTALL_OPTIONAL:-0}" == '1' ]]; then
 echo "Installing optional integrations at user request..."
 if command -v pacman >/dev/null; then sudo pacman -S --needed mpv fd ripgrep p7zip unzip zip libarchive sshfs libsecret ffmpeg rclone fuse3
 elif command -v apt-get >/dev/null; then sudo apt-get install -y mpv fd-find ripgrep p7zip-full unzip zip libarchive-tools sshfs libsecret-tools ffmpeg rclone fuse3; fi
else
 echo 'Optional integrations are not modified on upgrade (set NIRUORG_INSTALL_OPTIONAL=1 to opt in).'
fi
mkdir -p "$RELEASES" "$BIN" "$DESK" "$ICON" "$MIME/packages" "$STATE"; STAGE="$RELEASE_DIR.staging"; trap 'rm -rf "$STAGE"' ERR INT TERM; rm -rf "$STAGE"; mkdir -p "$STAGE"; cp -a "$SRC_DIR"/. "$STAGE"/
python3 -m py_compile "$STAGE/niruorg/app.py" "$STAGE/regression-suite.py" "$STAGE/gui-smoke-test.py" $(find "$STAGE" -maxdepth 1 -type f -name '*-test.py' -print)
python3 "$STAGE/regression-suite.py"
python3 "$STAGE/niruorg/app.py" --self-test
QT_QPA_PLATFORM=offscreen timeout 8s python3 "$STAGE/gui-smoke-test.py"
find "$STAGE" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true; find "$STAGE" -type f -name "*.py[co]" -delete 2>/dev/null || true
PREV=""; [ -L "$CURRENT" ] && PREV="$(readlink -f "$CURRENT" || true)"
if [[ "$PREV" == "$RELEASE_DIR" ]]; then
 echo 'This release is already active. Refusing in-place replacement; current files remain untouched.' >&2
 exit 1
fi
rm -rf "$RELEASE_DIR"; mv "$STAGE" "$RELEASE_DIR"; ln -sfn "$RELEASE_DIR" "$CURRENT.new"; mv -Tf "$CURRENT.new" "$CURRENT"
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
