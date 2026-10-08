from pathlib import Path
p=Path(__file__).parent/'niruorg/app.py'
s=p.read_text()
assert "VERSION='0.3.0'" in s
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
print('0.3.0 SSH agent portability / native unlock UX regression OK')
