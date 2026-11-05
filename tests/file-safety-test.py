#!/usr/bin/env python3
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); from source_contract import app_source, find_def, def_source  # noqa: E402
from pathlib import Path
import ast, tempfile, zipfile, tarfile, io, stat, os
src=app_source()
names=['_safe_archive_target','safe_extract_zip','safe_extract_tar']
found=[find_def(n,top_level=True) for n in names]; app=found[0][2]
nodes=[node for node,_,_ in found]
mod=ast.Module(body=nodes,type_ignores=[]); ns={'Path':Path,'zipfile':zipfile,'tarfile':tarfile,'stat':stat}
exec(compile(ast.fix_missing_locations(mod),str(app),'exec'),ns)
with tempfile.TemporaryDirectory() as td:
 root=Path(td); out=root/'out'; good=root/'good.zip'
 with zipfile.ZipFile(good,'w') as z:z.writestr('folder/ok.txt','ok')
 ns['safe_extract_zip'](good,out); assert (out/'folder/ok.txt').read_text()=='ok'
 evil=root/'evil.zip'
 with zipfile.ZipFile(evil,'w') as z:z.writestr('../escape.txt','bad')
 try:ns['safe_extract_zip'](evil,out); raise AssertionError('ZIP traversal was not blocked')
 except RuntimeError:pass
 assert not (root/'escape.txt').exists()
 linkzip=root/'link.zip'
 with zipfile.ZipFile(linkzip,'w') as z:
  i=zipfile.ZipInfo('link'); i.create_system=3; i.external_attr=(stat.S_IFLNK|0o777)<<16; z.writestr(i,'../../outside')
 try:ns['safe_extract_zip'](linkzip,out); raise AssertionError('ZIP symlink was not blocked')
 except RuntimeError:pass
 evil_tar=root/'evil.tar'
 with tarfile.open(evil_tar,'w') as t:
  data=b'bad'; m=tarfile.TarInfo('../escape2.txt'); m.size=len(data); t.addfile(m,io.BytesIO(data))
 try:ns['safe_extract_tar'](evil_tar,out); raise AssertionError('TAR traversal was not blocked')
 except RuntimeError:pass
 assert not (root/'escape2.txt').exists()
assert 'os.walk(src,followlinks=False)' in src and 'dest.symlink_to(os.readlink(link))' in src
assert 'class WorkBasketList' in src and 'Remove missing' in src and 'Rename Workspace' in src and 'Duplicate Workspace' in src
print('File Safety / workflow regression OK · 0.0.30')
