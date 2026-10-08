#!/usr/bin/env bash
set -Eeuo pipefail
BASE="$HOME/.local/share/niruorg"
RELEASES="$BASE/releases"
CURRENT="$BASE/current"
if [[ "${1:-}" == '--list' || "${1:-}" == '' ]]; then
  echo 'Installed NIRUORG releases:'
  if [[ -d "$RELEASES" ]]; then find "$RELEASES" -mindepth 1 -maxdepth 1 -type d ! -name '*.staging' -printf '%f\n' | sort -V; fi
  echo 'Current:'
  if [[ -L "$CURRENT" ]]; then readlink -f "$CURRENT"; else echo '(none)'; fi
  exit 0
fi
VERSION="$1"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then echo 'Expected version X.Y.Z' >&2; exit 2; fi
TARGET="$RELEASES/$VERSION"
if [[ ! -f "$TARGET/niruorg/app.py" ]]; then echo "Release not installed: $VERSION" >&2; exit 1; fi
if [[ ! -L "$CURRENT" ]]; then echo 'No active release symlink; refusing rollback.' >&2; exit 1; fi
PREV="$(readlink -f "$CURRENT")"
if [[ "$PREV" == "$TARGET" ]]; then echo "Already on $VERSION"; exit 0; fi
TMP="$BASE/.rollback-current.$$"
trap 'rm -f -- "$TMP"' EXIT
ln -s -- "$TARGET" "$TMP"
mv -Tf -- "$TMP" "$CURRENT"
if ! "$HOME/.local/bin/niruorg" --version >/dev/null 2>&1; then
  ln -s -- "$PREV" "$TMP"
  mv -Tf -- "$TMP" "$CURRENT"
  echo "Target failed version check; restored $PREV" >&2
  exit 1
fi
echo "NIRUORG active release: $VERSION"
echo "Previous release remains installed at $PREV"
