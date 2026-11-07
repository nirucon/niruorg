import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source, find_def, def_source  # noqa: E402
from pathlib import Path
import ast
s=app_source()
assert "VERSION='0.6.1'" in s
_node,_module_text,_=find_def('_ssh_agent_environment')
tree=ast.parse(_module_text)  # the module that defines the SSH agent parser
imports=set()
for node in tree.body:
    if isinstance(node, ast.Import):
        imports.update(alias.asname or alias.name.split('.')[0] for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        imports.add(node.module.split('.')[0] if node.module else '')
assert 're' in imports, 'SSH agent parser uses re.search but re is not imported'
segment=s[s.index('def _ssh_agent_environment'):s.index('def _stop_private_ssh_agent')]
assert 're.search(' in segment
assert "SSH_AUTH_SOCK" in segment and "SSH_AGENT_PID" in segment
assert "probe=subprocess.run(['ssh-add','-l']" not in segment
print('0.5.1 SSH agent parser/import regression OK')
