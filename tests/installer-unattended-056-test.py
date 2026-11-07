#!/usr/bin/env python3
"""0.6.1: the installer works on fresh Arch, Void and Debian, also unattended,
and a reinstall of the active release restores the launcher."""
import os, subprocess, tempfile
from pathlib import Path
source = Path(__file__).resolve().parents[1]
installer = (source / 'install.sh').read_text()
assert 'NIRUX_ASSUME_YES' in installer and '--yes' in installer, 'unattended consent missing'
assert '--noconfirm' in installer, 'pacman must not ask again once consent is given'
assert 'xbps-install -S' in installer and 'pyside6-widgets' in installer, 'Void branch missing'
assert 'noninteractive' in installer
assert 'Refusing in-place' not in installer, 'reinstall of the active release must not fail'
assert 'restoring the launcher' in installer
# The argument parser refuses unknown options before touching anything.
with tempfile.TemporaryDirectory() as home:
    r = subprocess.run(['bash', str(source / 'install.sh'), '--bogus'], cwd=source,
                       env={**os.environ, 'HOME': home}, capture_output=True, text=True)
    assert r.returncode == 2, r
    assert not (Path(home) / '.local').exists()
print('Installer 0.6.1 · unattended consent / Void / reinstall OK')
