#!/usr/bin/env python3
from pathlib import Path
s=Path('niruorg/app.py').read_text()
assert "VERSION='0.3.0'" in s
for x in ['Connections','Host / MagicDNS / IP','Tailscale · MagicDNS or 100.x IP','Tailscale SSH','FTPS · implicit TLS','Open SSH terminal','Connection details','ProxyJump','Keepalive','Verify TLS certificate']:
 assert x in s,x
assert "['tailscale'),'ssh',dest]" not in s  # guard malformed generated code
assert "shutil.which('tailscale'),'ssh',dest" in s
print('0.0.36 remote compatibility regression OK')
