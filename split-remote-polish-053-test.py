from pathlib import Path
s=Path('niruorg/app.py').read_text()
assert "VERSION='0.3.0'" in s
for needle in ["setHandleWidth(7)","_remember_split_sizes","_restore_split_sizes","_identify_remote_path","remote=self.owner._remote_definition_for_path(p)","return (name,cfg.get('protocol','sftp'),mp,cfg.get('path','/'))","return '/' + str(logical).lstrip('/')","REMOTE · {self.remote_name} · {self.remote_protocol}","LOCAL · {socket.gethostname()}"]:
 assert needle in s, needle
print("0.3.0 split / remote identity polish regression OK")
