#!/usr/bin/env python3
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
s=app_source()
assert "VERSION='0.6.0'" in s
for x in ['Connections','Host / MagicDNS / IP','Tailscale · MagicDNS or 100.x IP','Tailscale SSH','FTPS · implicit TLS','Open SSH terminal','Connection details','ProxyJump','Keepalive','Verify TLS certificate']:
 assert x in s,x
assert "['tailscale'),'ssh',dest]" not in s  # guard malformed generated code
assert "shutil.which('tailscale'),'ssh',dest" in s
print('0.0.36 remote compatibility regression OK')
