from pathlib import Path
s=Path('niruorg/app.py').read_text()
segment=s[s.index('  def unlock_prompt(n,v,retry):'):s.index('  def finish(ok,detail=',s.index('  def unlock_prompt(n,v,retry):'))]
for needle in ["QLineEdit.EchoMode.Password", "SSH_ASKPASS_REQUIRE':'force'", "pass_fds=(helper_fd_r,)", "pw.clear()", "helper.unlink(missing_ok=True)", "secret=''", "pw.returnPressed.connect(launch)"]:
 assert needle in segment, needle
for forbidden in ["run_detached(cmd", "kitty','--hold", "x-terminal-emulator"]:
 assert forbidden not in segment, forbidden
assert "VERSION='0.3.0'" in s
print('0.3.0 native SSH unlock regression OK')
