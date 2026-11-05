import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
s=app_source()
for x in ["VERSION='0.5.1'",'def import_connections','def _filezilla_sites','def _openssh_sites','def package_inspector','def system_diagnostics',"Proton Pass CLI · optional","secret-tool','store",'Import connections…']:
 assert x in s,x
assert "password':password" in s
print('0.5.1 milestone regression OK')
