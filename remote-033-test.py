from pathlib import Path
s=Path("niruorg/app.py").read_text()
assert "VERSION='0.4.0'" in s
assert "Save & connect" in s
assert "OpenSSH / Auto" in s
assert "MagicDNS / 100.x IP" in s
assert "SSH key is selected, but no private key file is configured" in s
assert "Connection details · " in s
assert "QMessageBox.information" not in s
assert "QMessageBox.warning" not in s
assert "QMessageBox.question" not in s
assert "def info(self,title,text)" in s and "def confirm(self,title,text,accept='Continue')" in s
print("0.0.36 remote UX regression OK")
