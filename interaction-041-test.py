from pathlib import Path
s=Path('niruorg/app.py').read_text()
assert "VERSION='0.3.0'" in s
assert 'class ImageViewerDialog(NiruDialog)' in s
assert 'self.image_viewer(files,idx(),True,d)' in s, 'Gallery viewer must be owned by modal Gallery dialog'
assert 'self.escape_handler' in s and "if state['fullscreen']:toggle_full()" in s
assert 'target=lab.contentsRect().size()' in s, 'Fit must use actual image viewport'
assert "QPushButton('Unlock SSH key…')" in s
assert "shutil.which('ssh-add')" in s
assert "OpenSSH / Auto" in s and "sshfs" in s
assert "NOW PLAYING" in s and "Space play/pause" in s
assert "state['manual']=True" in s, 'Player manual stop/track changes must not trigger auto-next race'
print('0.3.0 Gallery / Player / SFTP usability regression OK')
