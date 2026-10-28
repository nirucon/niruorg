#!/usr/bin/env python3
"""FileZilla XML import and portable server-config regression."""
from pathlib import Path
import ast, base64, tempfile, xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent
source = (root / 'niruorg/app.py').read_text(encoding='utf-8')

# The application-wide filter must fail open around deleted Qt wrappers. The
# native file picker creates/destroys layouts, which used to abort import.
assert 'except (RuntimeError,ReferenceError):' in source
assert 'Internal C++ object already deleted' in source
main_node = next(n for n in ast.walk(ast.parse(source))
                 if isinstance(n, ast.ClassDef) and n.name == 'Main')
main_filter = next(n for n in main_node.body
                   if isinstance(n, ast.FunctionDef) and n.name == 'eventFilter')
assert 'super().eventFilter' not in ast.get_source_segment(source, main_filter)

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
tree = ast.parse(source)
node = next(n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == '_filezilla_sites')
module = ast.Module(body=[node], type_ignores=[])
namespace = {'ET': ET, 'base64': base64}
exec(compile(ast.fix_missing_locations(module), str(root / 'niruorg/app.py'), 'exec'), namespace)
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
