import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
s=app_source()
assert "VERSION='0.6.0'" in s
assert 'def _ssh_agent_environment(self,create=False):' in s
assert "ssh-agent-{os.getpid()}.sock" in s
assert 'self._stop_private_ssh_agent()' in s
# Unlocking must stay native to NIRUORG; a terminal/detached ssh-add path is a regression.
unlock=s[s.index('  def unlock_prompt(n,v,retry):'):s.index('  def finish(ok,detail=',s.index('  def unlock_prompt(n,v,retry):'))]
assert "shutil.which('ssh-add')" in unlock
assert "SSH_ASKPASS_REQUIRE':'force'" in unlock
assert 'run_detached(' not in unlock
assert "poll.timeout.connect(check_unlocked)" not in unlock
assert "body.setTextFormat(Qt.TextFormat.PlainText)" in s
assert "SSH key needs to be unlocked</b>" not in s
print('0.5.1 SSH agent portability / native unlock UX regression OK')
