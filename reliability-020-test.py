from pathlib import Path
s=(Path(__file__).parent/'niruorg/app.py').read_text()
need=["VERSION='0.3.0'",'class MetadataWorker(QRunnable)','def _path_endpoint_meta','def _remote_path',"MetadataWorker('basket'","MetadataWorker('compare'","MetadataWorker('conflicts'",'Checking destination…','Available','Offline','Missing','Unavailable']
for x in need: assert x in s,x
# GUI-thread regressions fixed in 0.3.0
wb=s[s.index(' def show_dropzone'):s.index(' def _transfer_to_other_pane')]
assert 'missing=not p.exists()' not in wb
cmp=s[s.index(' def compare_panes'):s.index(' def choose_conflict_policy')]
assert 'left.iterdir()' not in cmp and 'right.iterdir()' not in cmp
print('0.3.0 reliability/workflow regression OK')
