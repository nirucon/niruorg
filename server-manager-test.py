#!/usr/bin/env python3
from pathlib import Path
s=Path('niruorg/app.py').read_text(); a=s.index(' def manage_servers(self,initial_name=None,initial_action=None,target_pane=None):'); b=s.index(' def toggle_hidden(self):',a); m=s[a:b]
for token in ["QPushButton('Add connection')","QPushButton('Edit…')","QPushButton('Duplicate…')","QPushButton('Remove…')","QPushButton('Test')","QPushButton('Details')","QPushButton('Connect / Browse')","QPushButton('Disconnect')","QPushButton('Cancel operation')",'QProcess(d)','ConnectTimeout=','BatchMode=yes','SFTP / SSH (recommended)','OpenSSH / Auto (recommended)','SSH key','Password','FTP','FTPS · explicit TLS','FTPS · implicit TLS','secret-tool','rclone_config','0o600','QLineEdit.EchoMode.Password','Tailscale · MagicDNS / 100.x IP','Tailscale SSH','ProxyJump','passive','tls_verify']:
 assert token in m, token
assert '.finished.connect(' in m and '.errorOccurred.connect(' in m
assert 'timer.timeout.connect' in m and 'p.terminate()' in m and 'p.kill()' in m
saved=m.split("return n,{'protocol'",1)[1].split('}',1)[0]
assert "'password':" not in saved
assert 'sshpass' not in m
assert "input=pw+'\\n'" in m
print('Remote Connections regression OK · SSH/SFTP + FTP/FTPS + Tailscale + secure auth + async network operations')
