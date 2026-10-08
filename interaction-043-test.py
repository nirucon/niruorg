from pathlib import Path

app = Path('niruorg/app.py').read_text()
install = Path('install.sh').read_text()
assert "VERSION='0.3.0'" in app

# Behavioural SSH unlock/retry contract. Do not pin user-facing prose: wording may
# legitimately improve without changing the security or retry behaviour.
segment = app[app.index('  def unlock_prompt(n,v,retry):'):app.index('  def finish(ok,detail=', app.index('  def unlock_prompt(n,v,retry):'))]
for needle in [
    'def ssh_preflight(',
    'def unlock_prompt(',
    'QLineEdit.EchoMode.Password',
    "shutil.which('ssh-add')",
    "SSH_ASKPASS_REQUIRE':'force'",
    'stdin=subprocess.DEVNULL',
    'pass_fds=(helper_fd_r,)',
    'pw.clear()',
    "secret=''",
    'helper.unlink(missing_ok=True)',
    'pw.returnPressed.connect(launch)',
    'QTimer.singleShot(0,retry)',
]:
    assert needle in app, needle

# Security invariants: no detached terminal unlock and no passphrase persisted
# through config/log/command arguments. The current implementation passes it to
# ssh-add through a short-lived inherited pipe used by SSH_ASKPASS.
for forbidden in ['run_detached(cmd', "kitty','--hold", 'x-terminal-emulator']:
    assert forbidden not in segment, forbidden
suite=Path('regression-suite.py').read_text()
assert "('interaction-043-test.py', False, 0)" in suite
print('0.3.0 SSH key unlock / retry behavioural regression OK')
