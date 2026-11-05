import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source  # noqa: E402
from pathlib import Path
s=app_source()
need=["VERSION='0.6.0'",'class MetadataWorker(QRunnable)','def _path_endpoint_meta','def _remote_path',"MetadataWorker('basket'","MetadataWorker('compare'","MetadataWorker('conflicts'",'Checking destination…','Available','Offline','Missing','Unavailable']
for x in need: assert x in s,x
# GUI-thread regressions fixed in 0.5.1
wb=s[s.index(' def show_dropzone'):s.index(' def _transfer_to_other_pane')]
assert 'missing=not p.exists()' not in wb
cmp=s[s.index(' def compare_panes'):s.index(' def choose_conflict_policy')]
assert 'left.iterdir()' not in cmp and 'right.iterdir()' not in cmp
print('0.5.1 reliability/workflow regression OK')
