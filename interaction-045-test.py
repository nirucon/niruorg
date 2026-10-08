from pathlib import Path
import re
root=Path(__file__).resolve().parent
app=(root/'niruorg/app.py').read_text()
install=(root/'install.sh').read_text()
assert "VERSION='0.4.0'" in app
assert "VERSION=\"0.4.0\"" in install
assert "SSH_AUTH_SOCK=([^;\\n]+)" in app
assert "for cmd in ([agent,'-a',str(requested_sock),'-s'],[agent,'-s'])" in app
assert "probe=subprocess.run(['ssh-add','-l']" not in app[app.index("def _ssh_agent_environment"):app.index("def _stop_private_ssh_agent")]
assert "sock.exists()" not in app[app.index("def _ssh_agent_environment"):app.index("def _stop_private_ssh_agent")]
print('0.4.0 SSH agent portability regression OK')
