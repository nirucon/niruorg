#!/usr/bin/env python3
from pathlib import Path
source=Path(__file__).parent
installer=(source/'install.sh').read_text()
assert 'VERSION="0.4.0"' in installer
assert installer.find("${NIRUORG_INSTALL_OPTIONAL:-0}")>=0, 'Optional packages must be opt-in'
assert installer.find('if [[ "$PREV" == "$RELEASE_DIR" ]]')>=0, 'Do not overwrite active release'
assert installer.find('mv -Tf "$CURRENT.new" "$CURRENT"')>=0, 'Missing atomic symlink activation'
assert '"$STAGE/regression-suite.py"' in installer, 'Regression suite not staged'
assert installer.count('gui-smoke-test.py') >= 1
assert (source/'rollback.sh').exists()
print('Installer safety 0.4.0 · opt-in integrations / staging / rollback helper OK')
