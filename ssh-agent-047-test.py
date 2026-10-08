from pathlib import Path
import ast
s=(Path(__file__).parent/'niruorg'/'app.py').read_text()
assert "VERSION='0.3.0'" in s
tree=ast.parse(s)
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
print('0.3.0 SSH agent parser/import regression OK')
