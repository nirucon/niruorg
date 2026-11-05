#!/usr/bin/env python3
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source, find_def, def_source  # noqa: E402
"""FileZilla XML import and portable server-config regression."""
from pathlib import Path
import ast, base64, tempfile, xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
source = app_source()

# The application-wide filter must fail open around deleted Qt wrappers. The
# native file picker creates/destroys layouts, which used to abort import.
assert 'except (RuntimeError,ReferenceError):' in source
assert 'Internal C++ object already deleted' in source
# Main's application-wide eventFilter (the one that feeds input diagnostics).
filters = []
for path in __import__('source_contract').source_files():
    text = path.read_text(encoding='utf-8')
    for n in ast.walk(ast.parse(text)):
        if isinstance(n, ast.FunctionDef) and n.name == 'eventFilter':
            seg = ast.get_source_segment(text, n) or ''
            if '_pane_for_event_target' in seg:
                filters.append(seg)
assert len(filters) == 1, len(filters)
assert 'super().eventFilter' not in filters[0]

# Sidebar places are real XDG locations and cloud folders are shown only when
# they exist. No hard-coded Desktop placeholder.
assert 'def _standard_sidebar_locations' in source
for token in ['DesktopLocation', 'DocumentsLocation', 'DownloadLocation',
              'PicturesLocation', 'MusicLocation', 'MoviesLocation',
              'PublicShareLocation', 'TemplatesLocation']:
    assert token in source, token
assert "if str(path)==str(home) or not path.is_dir():continue" in source
assert "if nc.is_dir():out.append(('Nextcloud'" in source

# Portable server definitions live in the synced Backup tree when available.
assert "Path.home()/'Nextcloud'/'Backup'/'niruorg'/'servers.json'" in source
assert "XDG_CONFIG_HOME" in source and "'niruorg'/'servers.json'" in source
assert 'def _load_servers' in source and 'def _write_server_store' in source
assert "if key=='servers_json':return self._load_servers()" in source
assert "if key=='servers_json':self._write_server_store(data)" in source

# Parse the actual FileZilla export shape with the production parser.
node, _, node_path = find_def('_filezilla_sites')
module = ast.Module(body=[node], type_ignores=[])
namespace = {'ET': ET, 'base64': base64}
exec(compile(ast.fix_missing_locations(module), str(node_path), 'exec'), namespace)
parser = namespace['_filezilla_sites']

xml = '''<?xml version="1.0" encoding="UTF-8"?>
<FileZilla3 version="3.71.1"><Servers>
 <Server><Host>ftp.example.test</Host><Port>21</Port><Protocol>0</Protocol>
  <User>ftp-user</User><Pass encoding="base64">c2VjcmV0</Pass>
  <Name>FTP test</Name><RemoteDir>/public</RemoteDir></Server>
 <Server><Host>sftp.example.test</Host><Port>2222</Port><Protocol>1</Protocol>
  <User>ssh-user</User><Name>SFTP test</Name></Server>
 <Server><Host>ftps.example.test</Host><Port>990</Port><Protocol>3</Protocol>
  <User>tls-user</User><Pass encoding="base64">dGxzLXNlY3JldA==</Pass>
  <Name>FTPS test</Name></Server>
</Servers></FileZilla3>'''
with tempfile.TemporaryDirectory() as tmp:
    sample = Path(tmp) / 'FileZilla.xml'
    sample.write_text(xml, encoding='utf-8')
    sites = parser(None, sample)

assert len(sites) == 3
assert sites[0]['cfg']['protocol'] == 'ftp'
assert sites[0]['cfg']['port'] == 21
assert sites[0]['cfg']['path'] == '/public'
assert sites[0]['password'] == 'secret'
assert sites[1]['cfg']['protocol'] == 'sftp'
assert sites[1]['cfg']['port'] == 2222
assert sites[1]['cfg']['auth'] == 'auto'
assert sites[2]['cfg']['protocol'] == 'ftps-implicit'
assert sites[2]['password'] == 'tls-secret'

print('FileZilla import / sidebar / portable server store regression OK')
