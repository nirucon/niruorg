import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
s=app_source()
segment=s[s.index('  def unlock_prompt(n,v,retry):'):s.index('  def finish(ok,detail=',s.index('  def unlock_prompt(n,v,retry):'))]
for needle in ["QLineEdit.EchoMode.Password", "SSH_ASKPASS_REQUIRE':'force'", "pass_fds=(helper_fd_r,)", "pw.clear()", "helper.unlink(missing_ok=True)", "secret=''", "pw.returnPressed.connect(launch)"]:
 assert needle in segment, needle
for forbidden in ["run_detached(cmd", "kitty','--hold", "x-terminal-emulator"]:
 assert forbidden not in segment, forbidden
assert "VERSION='0.6.0'" in s
print('0.5.1 native SSH unlock regression OK')
