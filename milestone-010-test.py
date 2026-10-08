from pathlib import Path
s=Path('niruorg/app.py').read_text()
for x in ["VERSION='0.4.0'",'def import_connections','def _filezilla_sites','def _openssh_sites','def package_inspector','def system_diagnostics',"Proton Pass CLI · optional","secret-tool','store",'Import connections…']:
 assert x in s,x
assert "password':password" in s
print('0.4.0 milestone regression OK')
