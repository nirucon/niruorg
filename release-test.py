#!/usr/bin/env python3
from pathlib import Path
import ast,re
root=Path(__file__).parent
app=(root/'niruorg/app.py').read_text()
install=(root/'install.sh').read_text(); suite=(root/'regression-suite.py').read_text()
smoke=(root/'gui-smoke-test.py').read_text(); shortcut=(root/'shortcut-test.py').read_text(); delete_test=(root/'permanent-delete-test.py').read_text()
v=re.search(r"VERSION='([^']+)'",app).group(1)
assert f'VERSION="{v}"' in install
assert 'python3 "$STAGE/regression-suite.py"' in install
for required_test in ['upgrade-safety-test.py','file-safety-test.py','remote-031-test.py','workflow-test.py']:
    assert required_test in suite, f'{required_test} missing from regression manifest'
assert 'pane1' in smoke and '.view.model()' in smoke
assert 'w.view' not in smoke
assert 'selected()) == 0' in smoke
assert 'update_breadcrumbs' in app and 'undo_last' in app
assert "self.date_format=self.s.value('date_format','Swedish')" in app
assert "dt.toString('yyyy-MM-dd HH:mm')" in app
assert 'smart_view' in app and 'operation_history' in app
assert 'def storage_view' in app and 'def permissions_view' in app and 'def operation_queue' in app
assert 'def _sidebar_section' in app and 'collapsed_sections' in app
assert 'def build_quicklook' in app and 'def toggle_quicklook' in app and 'quicklook_requested' in app
assert 'def add_shortcuts' in app and "'SHORTCUTS'" in app
assert 'def compare_panes' in app
assert 'def jump' in app and 'def toggle_focus' in app and 'def find_files' in app
assert "f.addRow('Date & time',self.datefmt)" in app
assert 'currentTextChanged.connect(self.preview_theme)' in app
assert 'def _copy_tree' in app
assert 'def clipboard_inspector' in app and 'def folder_health' in app and 'def duplicate_finder' in app and 'def saved_searches' in app
assert 'saved_searches_json' in app
assert 'def show_keybindings' in app and 'def quick_create' in app and 'def forward' in app
assert "'Shift+Delete','Delete Permanently…'" in app and "'Alt+Left','Back'" in app
assert 'Minimal but powerful file organizer for Linux.' in app
assert 'def image_viewer' in app and 'QTimer.singleShot(1,batch)' in app
assert 'def _copy_file' in app and '4*1024*1024' in app
assert 'def integrations' in app and 'def nextcloud_share' in app and 'def media_info' in app
assert 'class BrowserTree(QTreeView)' in app and 'def keyPressEvent' in app and "'Shift+Delete'" in app
assert 'def archive_browser' in app and 'Unsafe archive path blocked' in app
assert 'def temporary_split' in app and 'def path_actions' in app
assert "VERSION='0.4.0'" in app
assert f"assert VERSION=='{v}'" in app, 'Self-test VERSION assertion is stale'
assert 'Shortcut regression OK' in shortcut and 'Shift+Delete' in shortcut
assert 'Permanent delete regression OK' in delete_test and '_confirm_permanent_delete' in app
assert 'QMessageBox.StandardButton.Delete' not in app
assert 'def manage_niru_actions' in app and 'def manage_recipes' in app and 'niru_actions_json' in app and 'recipes_json' in app
assert "target.name+'.niruorg-part'" in app and 'os.replace(partial,target)' in app
assert "VERSION='0.4.0'" in app
ast.parse(app); ast.parse(smoke); ast.parse(shortcut); ast.parse(delete_test)
assert (root/'assets/niruorg.svg').exists()
print(f'Release contract OK · {v}')

assert 'Delete Permanently…' in app
assert 'Input diagnostics…' in app
assert 'input-diagnostics.log' in app
assert 'def open_with' in app and 'def file_associations' in app and 'xdg-mime' in app
assert 'application/x-nirupres' in app and 'text/markdown' in app
assert 'def context_lens' in app and 'Git repository' in app
assert 'def closeEvent' in app and 'session_pane1' in app and 'session_split' in app

assert (root/'mime/nirupres.xml').exists()
assert 'update-mime-database' in install

assert 'def manage_clouds' in app and 'def open_cloud' in app and 'def unmount_cloud' in app
assert "self._sidebar_section('cloud','CLOUD',self._cloud_sidebar_entries(),True)" in app
assert 'def close_split' in app and 'rclone' in install

# Regression tests are registered once in regression-suite.py and each is executed
# by a separate subprocess. The runner also rejects unregistered *-test.py files.
for test in ['server-manager-test.py','search-compare-test.py','workflow-029-test.py','file-safety-test.py','remote-031-test.py','sidebar-server-032-test.py','interaction-038-test.py']:
    assert test in suite, f'{test} missing from regression manifest'
assert "ROOT.glob('*-test.py')" in suite
assert 'unregistered = sorted(discovered - declared)' in suite
assert 'subprocess.run(' in suite
assert 'box=NiruDialog(d)' in app
assert 'box.raise_()' not in app
