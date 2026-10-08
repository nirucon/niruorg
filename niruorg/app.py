#!/usr/bin/env python3
import os,sys,shutil,subprocess,mimetypes,zipfile,tarfile,stat,json,urllib.request,urllib.parse,base64,shlex,socket,tempfile,time,re,hashlib,uuid,xml.etree.ElementTree as ET
from pathlib import Path
from PySide6.QtCore import QPointF,Qt,QDir,QUrl,QSettings,QModelIndex,QEvent,QSortFilterProxyModel,QRegularExpression,QSize,QFile,QTimer,QRunnable,QThreadPool,Signal,QObject,QProcess,QMimeData
from PySide6.QtGui import QAction,QKeySequence,QDesktopServices,QPixmap,QIcon,QShortcut,QColor,QPainter,QPen,QBrush,QPolygonF,QCursor,QDrag
from PySide6.QtWidgets import *
from PySide6.QtWidgets import QFileIconProvider
try:
 from .transfer_safety import TransferSafetyError,verified_partial_offset,guard_transfer_locations
except ImportError:  # Direct execution via installer's app.py launcher
 from transfer_safety import TransferSafetyError,verified_partial_offset,guard_transfer_locations
APP='NIRUORG'; VERSION='0.4.0'
THEMES={
 'Niru Noir':{'bg':'#090909','fg':'#ededed','muted':'#858585','panel':'#141414','surface':'#1b1b1b','border':'#292929','accent':'#bdbdbd','accentfg':'#090909','sel':'#333333','danger':'#d56b6b'},
 'C. Larsson':{'bg':'#eee5d1','fg':'#29251f','muted':'#776d5e','panel':'#e2d3b7','surface':'#e8dcc5','border':'#bbaa8d','accent':'#745c3e','accentfg':'#fffaf0','sel':'#d3c19f','danger':'#9c3d32'},
 'Satie':{'bg':'#ddd5c4','fg':'#292b29','muted':'#737168','panel':'#cbc2af','surface':'#d3cbb9','border':'#aaa18f','accent':'#4f4c45','accentfg':'#f5f0e7','sel':'#bbb6a9','danger':'#8b4a46'},
 'Nord':{'bg':'#2e3440','fg':'#eceff4','muted':'#9aa4b2','panel':'#3b4252','surface':'#434c5e','border':'#4c566a','accent':'#88c0d0','accentfg':'#2e3440','sel':'#434c5e','danger':'#bf616a'},
}
def human(n):
 try:n=float(n)
 except:return '—'
 for u in ['B','KB','MB','GB','TB']:
  if n<1024:return f'{n:.0f} {u}' if u=='B' else f'{n:.1f} {u}'
  n/=1024
 return f'{n:.1f} PB'
def _safe_archive_target(base,name):
 base=Path(base).resolve(); target=(base/name).resolve()
 if target!=base and base not in target.parents:raise RuntimeError(f'Unsafe archive path blocked: {name}')
 return target
def safe_extract_zip(archive,out,members=None):
 base=Path(out).resolve(); base.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(archive) as z:
  chosen=z.infolist() if members is None else [z.getinfo(n) for n in members]
  for info in chosen:
   _safe_archive_target(base,info.filename)
   # ZIP symlinks can point outside the destination; do not materialize them.
   mode=(info.external_attr >> 16) & 0o170000
   if mode==stat.S_IFLNK:raise RuntimeError(f'Archive symlink blocked: {info.filename}')
  for info in chosen:z.extract(info,base)
def safe_extract_tar(archive,out,members=None):
 base=Path(out).resolve(); base.mkdir(parents=True,exist_ok=True)
 with tarfile.open(archive) as t:
  chosen=t.getmembers() if members is None else [t.getmember(n) for n in members]
  for m in chosen:
   _safe_archive_target(base,m.name)
   if m.issym() or m.islnk():raise RuntimeError(f'Archive link blocked: {m.name}')
  t.extractall(base,members=chosen,filter='data')
def run_detached(args,cwd=None,env=None):
 try:
  pe=os.environ.copy(); pe.update(env or {})
  subprocess.Popen(args,cwd=cwd,env=pe,start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); return True
 except Exception:return False
def omarchy_palette():
 candidates=[Path.home()/'.local/state/omarchy/current/theme/colors.toml',Path.home()/'.local/state/omarchy/current/colors.toml']
 p=next((x for x in candidates if x.exists()),None)
 if not p:return None
 vals={}
 try:
  for line in p.read_text(errors='ignore').splitlines():
   if '=' in line:
    k,v=line.split('=',1); vals[k.strip()]=v.strip().strip('"\'')
  def c(*keys,default):
   for k in keys:
    v=vals.get(k)
    if v and v.startswith('#'):return v
   return default
  bg=c('background',default='#090909'); fg=c('foreground',default='#ededed'); accent=c('accent','color4','blue',default='#bdbdbd')
  return {'bg':bg,'fg':fg,'muted':c('color8','bright_black',default='#858585'),'panel':c('color0','black',default='#141414'),'surface':c('color0','black',default='#1b1b1b'),'border':c('color8','bright_black',default='#292929'),'accent':accent,'accentfg':bg,'sel':c('selection_background','color8',default='#333333'),'danger':c('color1','red',default='#d56b6b')}
 except:return None
class NiruDialog(QDialog):
 def keyPressEvent(self,event):
  if event.key()==Qt.Key.Key_Escape:
   self.reject(); event.accept(); return
  super().keyPressEvent(event)
 def showEvent(self,event):
  # Every ordinary NIRUORG popup must have an obvious keyboard/mouse exit.
  # Dialogs that already expose Close/Cancel/OK/Save keep their own controls.
  super().showEvent(event)
  if self.property('_niru_close_checked') or self.isFullScreen():return
  self.setProperty('_niru_close_checked',True)
  exits=('close','cancel','ok','save','done')
  buttons=self.findChildren(QPushButton)
  if any(b.isVisible() and b.isEnabled() and b.text().replace('&','').strip().lower() in exits for b in buttons):return
  lay=self.layout()
  if lay is None:return
  close=QPushButton('Close',self); close.setObjectName('niruAutoClose'); close.clicked.connect(self.reject)
  if isinstance(lay,QFormLayout):lay.addRow('',close)
  elif isinstance(lay,QBoxLayout):
   row=QHBoxLayout(); row.addStretch(); row.addWidget(close); lay.addLayout(row)
  elif isinstance(lay,QGridLayout):lay.addWidget(close,lay.rowCount(),max(0,lay.columnCount()-1))
class ImageViewerDialog(NiruDialog):
 def __init__(self,parent=None):
  super().__init__(parent); self.escape_handler=None; self.resize_handler=None
 def keyPressEvent(self,event):
  if event.key()==Qt.Key.Key_Escape and self.escape_handler:
   self.escape_handler(); event.accept(); return
  super().keyPressEvent(event)
 def resizeEvent(self,event):
  super().resizeEvent(event)
  if self.resize_handler:QTimer.singleShot(0,self.resize_handler)
class SemanticIconProvider(QFileIconProvider):
 def __init__(self,pal):super().__init__(); self.pal=pal
 def set_palette(self,pal):self.pal=pal
 def _icon(self,kind):
  pm=QPixmap(32,32); pm.fill(Qt.GlobalColor.transparent); q=QPainter(pm); q.setRenderHint(QPainter.RenderHint.Antialiasing)
  fg=QColor(self.pal.get('muted','#888')); ac=QColor(self.pal.get('accent','#bbb')); bg=QColor(self.pal.get('surface','#222'))
  pen=QPen(ac if kind in ('folder','drive') else fg,1.7); q.setPen(pen); q.setBrush(QBrush(bg))
  if kind=='folder':
   q.drawRoundedRect(4,10,24,16,2,2); q.drawRoundedRect(6,7,10,6,2,2)
  elif kind=='drive':
   q.drawRoundedRect(5,8,22,17,3,3); q.drawLine(8,20,24,20); q.setBrush(QBrush(ac)); q.drawEllipse(21,22,2,2)
  elif kind=='image':
   q.drawRoundedRect(6,5,20,22,2,2); q.drawEllipse(10,9,4,4); q.drawLine(8,23,14,17); q.drawLine(14,17,18,21); q.drawLine(18,21,24,15)
  elif kind=='media':
   q.drawRoundedRect(6,5,20,22,2,2); q.setBrush(QBrush(ac)); q.drawPolygon(QPolygonF([QPointF(13,11),QPointF(13,21),QPointF(21,16)]))
  elif kind=='archive':
   q.drawRoundedRect(7,5,18,22,2,2); q.drawLine(16,6,16,21); q.drawLine(13,10,16,10); q.drawLine(16,14,19,14); q.drawLine(13,18,16,18)
  else:
   q.drawRoundedRect(7,4,18,24,2,2); q.drawLine(11,11,21,11); q.drawLine(11,16,21,16); q.drawLine(11,21,18,21)
  q.end(); return QIcon(pm)
 def icon(self,arg):
  try:
   if hasattr(arg,'isDir') and arg.isDir(): return self._icon('folder')
   name=arg.fileName().lower() if hasattr(arg,'fileName') else ''
   mime=mimetypes.guess_type(name)[0] or ''
   if mime.startswith('image/'):return self._icon('image')
   if mime.startswith('audio/') or mime.startswith('video/'):return self._icon('media')
   if name.endswith(('.zip','.7z','.rar','.tar','.gz','.xz','.zst','.bz2')):return self._icon('archive')
  except Exception:pass
  return self._icon('file')
def mounted_paths():
 """Read kernel mount metadata without touching the mounted filesystems."""
 out=set()
 try:
  for line in Path('/proc/self/mountinfo').read_text(errors='replace').splitlines():
   fields=line.split()
   if len(fields)>4:
    raw=fields[4].replace('\\040',' ').replace('\\011','\\t').replace('\\134','\\')
    out.add(os.path.normpath(raw))
 except Exception:pass
 return out

def path_is_mounted(path,mounts=None):
 return os.path.normpath(os.path.abspath(os.path.expanduser(str(path)))) in (mounts if mounts is not None else mounted_paths())

def lexical_under(path,base):
 try:
  p=os.path.normpath(os.path.abspath(os.path.expanduser(str(path))))
  b=os.path.normpath(os.path.abspath(os.path.expanduser(str(base))))
  return p==b or p.startswith(b+os.sep)
 except Exception:return False

class RemoteProbeSignals(QObject):
 done=Signal(object)
class RemoteProbeWorker(QRunnable):
 """Probe a FUSE path outside the GUI thread with a strict subprocess timeout."""
 def __init__(self,token,path,mount):
  super().__init__(); self.token=token; self.path=str(path); self.mount=str(mount); self.signals=RemoteProbeSignals()
 def run(self):
  result={'token':self.token,'path':self.path,'mount':self.mount,'ok':False,'detail':'Unavailable'}
  if not path_is_mounted(self.mount):
   result['detail']='Offline'; self.signals.done.emit(result); return
  statbin=shutil.which('stat') or '/usr/bin/stat'
  try:
   r=subprocess.run([statbin,'-L','--format=%F',self.path],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2.5)
   result['ok']=r.returncode==0; result['detail']='Connected' if result['ok'] else 'Unavailable'
  except subprocess.TimeoutExpired:result['detail']='Unavailable · timed out'
  except Exception as e:result['detail']='Unavailable · '+str(e)
  self.signals.done.emit(result)

class DiscoverySignals(QObject):
 done=Signal(object)
class DiscoveryWorker(QRunnable):
 """Discover external integrations without touching remote/FUSE paths."""
 def __init__(self):super().__init__(); self.signals=DiscoverySignals()
 def run(self):
  result={'cloud':[],'types':{},'devices':[]}
  exe=shutil.which('rclone')
  if exe:
   try:
    r=subprocess.run([exe,'listremotes'],capture_output=True,text=True,timeout=4)
    if r.returncode==0:result['cloud']=[x.strip().rstrip(':') for x in r.stdout.splitlines() if x.strip()]
   except Exception:pass
  # Mount-table metadata only: never dereference external/FUSE paths here.
  for mp in mounted_paths():
   if mp.startswith('/mnt/') or mp.startswith('/run/media/') or mp.startswith('/media/'):result['devices'].append(mp)
  self.signals.done.emit(result)

class MetadataSignals(QObject):
 done=Signal(object); failed=Signal(str)
class MetadataWorker(QRunnable):
 """Bounded metadata discovery. Remote/FUSE paths are only touched in subprocesses with timeouts."""
 def __init__(self,mode,payload):super().__init__(); self.mode=mode; self.payload=payload; self.signals=MetadataSignals()
 def _remote_stat(self,path,timeout=2.5):
  statbin=shutil.which('stat') or '/usr/bin/stat'
  try:
   r=subprocess.run([statbin,'-L','--format=%F\\t%s\\t%Y',str(path)],capture_output=True,text=True,timeout=timeout)
   if r.returncode!=0:return {'state':'missing'}
   parts=r.stdout.strip().split('\\t'); typ=parts[0] if parts else ''
   return {'state':'available','dir':'directory' in typ.lower(),'size':int(parts[1]) if len(parts)>1 and parts[1].isdigit() else 0,'mtime':float(parts[2]) if len(parts)>2 else 0}
  except subprocess.TimeoutExpired:return {'state':'offline'}
  except Exception:return {'state':'unavailable'}
 def _local_stat(self,path):
  try:
   p=Path(path); st=p.stat(); return {'state':'available','dir':p.is_dir(),'size':st.st_size,'mtime':st.st_mtime}
  except FileNotFoundError:return {'state':'missing'}
  except OSError:return {'state':'unavailable'}
 def _stat(self,item):
  if item.get('remote') and not item.get('mounted'):return {'state':'offline'}
  return self._remote_stat(item['path']) if item.get('remote') else self._local_stat(item['path'])
 def _list(self,side):
  path=side['path']
  if side.get('remote') and not side.get('mounted'):return None,'Offline'
  if side.get('remote'):
   find=shutil.which('find') or '/usr/bin/find'
   try:
    r=subprocess.run([find,path,'-mindepth','1','-maxdepth','1','-printf','%f\\t%y\\t%s\\t%T@\\n'],capture_output=True,text=True,timeout=4)
    if r.returncode!=0:return None,'Unavailable'
    out={}
    for line in r.stdout.splitlines():
     parts=line.split('\\t')
     if len(parts)>=4:
      name,typ,size,mt=parts[:4]; out[name]={'dir':typ=='d','size':int(size or 0),'mtime':float(mt or 0)}
    return out,None
   except subprocess.TimeoutExpired:return None,'Timed out'
   except Exception as e:return None,str(e)
  try:
   out={}
   with os.scandir(path) as it:
    for e in it:
     try:st=e.stat(follow_symlinks=False); out[e.name]={'dir':e.is_dir(follow_symlinks=False),'size':st.st_size,'mtime':st.st_mtime}
     except OSError:out[e.name]={'dir':False,'size':0,'mtime':0}
   return out,None
  except Exception as e:return None,str(e)
 def run(self):
  try:
   if self.mode=='basket':
    rows=[]
    for item in self.payload:rows.append(dict(item,meta=self._stat(item)))
    self.signals.done.emit({'mode':'basket','rows':rows}); return
   if self.mode=='conflicts':
    conflicts=[]
    for item in self.payload:
     meta=self._stat(item)
     if meta.get('state')=='available':conflicts.append(item['path'])
    self.signals.done.emit({'mode':'conflicts','conflicts':conflicts}); return
   if self.mode=='compare':
    left,le=self._list(self.payload['left']); right,re=self._list(self.payload['right'])
    self.signals.done.emit({'mode':'compare','left':left,'right':right,'left_error':le,'right_error':re}); return
  except Exception as e:self.signals.failed.emit(str(e))

class StartupTrace:
 def __init__(self):
  self.t0=time.perf_counter(); self.last=self.t0; self.path=Path.home()/'.local/state/niruorg/startup.log'
  try:self.path.parent.mkdir(parents=True,exist_ok=True)
  except Exception:pass
 def mark(self,label):
  now=time.perf_counter(); total=(now-self.t0)*1000; delta=(now-self.last)*1000; self.last=now
  try:
   with self.path.open('a',encoding='utf-8') as f:f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")}  {label:<30} {total:8.1f} ms  (+{delta:.1f})\n')
  except Exception:pass

class WorkerSignals(QObject):
 progress=Signal(int,int,str); activity=Signal(object); done=Signal(object); failed=Signal(str)
class ConnectionDiagnosticSignals(QObject):
 done=Signal(object)
class ConnectionDiagnosticWorker(QRunnable):
 def __init__(self,name,cfg):
  super().__init__(); self.name=name; self.cfg=dict(cfg); self.signals=ConnectionDiagnosticSignals()
 def run(self):
  v=self.cfg; host=v.get('host','').strip(); port=int(v.get('port',22)); timeout=max(2,min(8,int(v.get('timeout',12)))); rows=[]
  def add(stage,ok,detail):rows.append((stage,bool(ok),str(detail)))
  try:
   infos=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM); ips=[]
   for info in infos:
    ip=info[4][0]
    if ip not in ips:ips.append(ip)
   add('DNS / host',True,', '.join(ips[:4]))
  except Exception as e:
   add('DNS / host',False,e); self.signals.done.emit(rows); return
  if v.get('route','direct').startswith('tailscale'):
   ts=shutil.which('tailscale')
   if not ts:add('Tailscale',False,'tailscale CLI is not installed')
   else:
    try:
     r=subprocess.run([ts,'ping','--c','1','--timeout','3s',host],capture_output=True,text=True,timeout=5); out=(r.stdout or r.stderr).strip().splitlines(); add('Tailscale',r.returncode==0,out[-1] if out else f'exit {r.returncode}')
    except Exception as e:add('Tailscale',False,e)
  try:
   with socket.create_connection((host,port),timeout=min(4,timeout)) as sock:
    peer=sock.getpeername(); add(f'TCP/{port}',True,f'{peer[0]}:{peer[1]} accepted connection')
  except Exception as e:
   add(f'TCP/{port}',False,e); self.signals.done.emit(rows); return
  if v.get('protocol','sftp').lower()=='sftp':
   ssh=shutil.which('ssh')
   if not ssh:add('OpenSSH',False,'ssh client is not installed')
   else:
    dest=(f'{v.get("user")}@' if v.get('user') else '')+host
    args=[ssh,'-p',str(port),'-o',f'ConnectTimeout={timeout}','-o','BatchMode=yes','-o','ServerAliveCountMax=1']
    pj=v.get('proxyjump','').strip()
    if pj:args += ['-J',pj]
    if v.get('auth','auto').lower()=='key' and v.get('key'):
     key=str(Path(os.path.expanduser(v.get('key')))); args += ['-i',key,'-o','IdentitiesOnly=yes']
    args += [dest,'true']
    try:
     r=subprocess.run(args,capture_output=True,text=True,timeout=timeout+3); out=(r.stderr or r.stdout).strip(); low=out.lower()
     if r.returncode==0:add('SSH authentication',True,'public-key / OpenSSH authentication succeeded')
     elif 'permission denied' in low or 'publickey' in low:add('SSH authentication',False,(out[-500:] if out else 'authentication rejected')+' · unlock the SSH key or check the configured identity')
     else:add('SSH handshake',False,out[-500:] if out else f'ssh exited {r.returncode}')
    except subprocess.TimeoutExpired:add('SSH handshake',False,'timed out')
    except Exception as e:add('SSH handshake',False,e)
  self.signals.done.emit(rows)
class TransferWorker(QRunnable):
 """Copy/move worker. Publish files and folders only after a completed staging copy.

 A partial file is reusable only after its contents match the current source.
 Replacing an existing destination never deletes it before the replacement is ready.
 """
 def __init__(self,items,dst,move=False,policy='ask'):
  super().__init__(); self.items=[Path(x) for x in items]; self.dst=Path(dst); self.move=move; self.policy=policy; self.signals=WorkerSignals(); self.cancelled=False
 def cancel(self):self.cancelled=True
 def _target(self,src):
  target=self.dst/src.name
  if not target.exists() and not target.is_symlink():return target
  if self.policy=='skip':return None
  if self.policy=='replace':return target  # Publish new data before replacing old data.
  if self.policy=='keepboth':
   stem,suffix=src.stem,src.suffix; n=2
   while target.exists() or target.is_symlink():
    target=self.dst/f'{stem} ({n}){suffix}'; n+=1
   return target
  raise FileExistsError(f'{target.name} already exists in {self.dst}')
 def _copy_file(self,src,target,allow_resume=True):
  # Never expose a half-copied file as the final destination. Copy beside the
  # target and atomically publish it only after the full write succeeds.
  if target.is_dir() and not target.is_symlink():raise TransferSafetyError('Refusing to replace a directory with a file')
  partial=target.with_name(target.name+'.niruorg-part') if allow_resume else target.with_name('.niruorg-stagepart-'+uuid.uuid4().hex)
  if partial.is_symlink():raise TransferSafetyError('Refusing to use a symlink as a partial file')
  try:
   with src.open('rb') as r:
    initial=os.fstat(r.fileno()); total=initial.st_size
    # Compare ALL partial bytes against the source before trusting an offset.
    # Different-source or corrupted partials are refused, never silently resumed.
    existing=partial.exists()
    offset=verified_partial_offset(src,partial) if existing else 0
    if offset>total:raise TransferSafetyError('Partial file exceeds source size')
    flags=os.O_WRONLY|os.O_NOFOLLOW
    if existing:
     fd=os.open(partial,flags|os.O_APPEND)
    else:
     fd=os.open(partial,flags|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'ab' if offset else 'wb') as w:
     if existing:
      r.seek(offset)
      if os.fstat(w.fileno()).st_size!=offset:raise TransferSafetyError('Partial changed during verification')
     done=offset
     while True:
      if self.cancelled:return False  # Keep verified partial for retry.
      chunk=r.read(4*1024*1024)
      if not chunk:break
      w.write(chunk); done+=len(chunk); self.signals.activity.emit({'name':src.name,'bytes_done':done,'bytes_total':total}); self.signals.progress.emit(done,max(1,total),src.name)
     w.flush(); os.fsync(w.fileno())
     final=os.fstat(r.fileno())
     if done!=total or (final.st_size,final.st_mtime_ns,final.st_ino)!=(initial.st_size,initial.st_mtime_ns,initial.st_ino):
      raise TransferSafetyError('Source changed during transfer; destination was not replaced')
   shutil.copystat(src,partial,follow_symlinks=False)
   if self.policy!='replace' and (target.exists() or target.is_symlink()):
    raise FileExistsError(f'Destination appeared during transfer: {target}')
   os.replace(partial,target)
   return True
  except Exception:
   # Deliberately retain regular partial files for inspection/retry. Never
   # remove or overwrite an existing destination following a copy failure.
   raise
 def _copy_tree(self,src,target):
  target.mkdir(parents=True,exist_ok=False); files=[]
  for root,dirs,names in os.walk(src,followlinks=False):
   if self.cancelled:return False
   rel=Path(root).relative_to(src); out=target/rel; out.mkdir(parents=True,exist_ok=True)
   # Preserve directory symlinks as links and never traverse their targets.
   for name in list(dirs):
    link=Path(root)/name
    if link.is_symlink():
     dest=out/name; dest.symlink_to(os.readlink(link)); dirs.remove(name)
   for name in names:files.append((Path(root)/name,out/name))
  total=max(1,len(files))
  for pos,(a,b) in enumerate(files,1):
   if self.cancelled:return False
   b.parent.mkdir(parents=True,exist_ok=True)
   if a.is_symlink():b.symlink_to(os.readlink(a))
   elif not self._copy_file(a,b,allow_resume=False):return False
   self.signals.progress.emit(pos,total,a.name)
  try:shutil.copystat(src,target,follow_symlinks=False)
  except OSError:pass
  return True
 def _publish_tree(self,src,target):
  # Stage within the destination filesystem. A cancelled copy never deletes
  # an existing directory; replacement has a rollback path on rename failure.
  stage_root=Path(tempfile.mkdtemp(prefix='.niruorg-stage-',dir=self.dst))
  staged=stage_root/src.name
  try:
   if not self._copy_tree(src,staged):return False
   if self.cancelled:return False
   if target.exists() or target.is_symlink():
    if self.policy!='replace':raise FileExistsError(f'{target} appeared during copy')
    backup_root=Path(tempfile.mkdtemp(prefix='.niruorg-backup-',dir=self.dst))
    backup=backup_root/target.name
    try:
     os.replace(target,backup)
     try:os.replace(staged,target)
     except BaseException:
      os.replace(backup,target)
      raise
     # Only now may the previous destination be removed.
     if backup.is_dir() and not backup.is_symlink():shutil.rmtree(backup)
     else:backup.unlink()
    finally:
     try:backup_root.rmdir()
     except OSError:pass  # Keep a recoverable backup if cleanup fails.
   else:os.replace(staged,target)
   return True
  finally:
   if stage_root.exists():shutil.rmtree(stage_root)
 def _copy_symlink(self,src,target):
  if target.is_dir() and not target.is_symlink():raise TransferSafetyError('Refusing to replace a directory with a symlink')
  tmp=target.with_name(target.name+'.niruorg-link-'+str(os.getpid())+'-'+str(id(self)))
  try:
   tmp.symlink_to(os.readlink(src))
   if self.policy!='replace' and (target.exists() or target.is_symlink()):
    raise FileExistsError(f'Destination appeared during transfer: {target}')
   os.replace(tmp,target)
  finally:
   if tmp.is_symlink():tmp.unlink()
 def run(self):
  changes=[]
  try:
   self.dst.mkdir(parents=True,exist_ok=True); total=len(self.items)
   for pos,src in enumerate(self.items,1):
    if self.cancelled:break
    self.signals.progress.emit(pos-1,total,src.name)
    target=self._target(src)
    if target is None:continue
    guard_transfer_locations(src,target)
    replaced=target.exists() or target.is_symlink()
    old=str(src)
    if src.is_symlink():
     self._copy_symlink(src,target)
     if self.move:src.unlink()
    elif src.is_file():
     if not self._copy_file(src,target):break
     if self.move:src.unlink()
    elif src.is_dir():
     if not self._publish_tree(src,target):break
     if self.move:shutil.rmtree(src)
    else:raise TransferSafetyError(f'Unsupported source type: {src}')
    changes.append({'src':old,'dst':str(target),'move':self.move,'replaced':replaced})
    if not src.is_file():self.signals.progress.emit(pos,total,src.name)
   state='Cancelled' if self.cancelled else ('Moved' if self.move else 'Copied')
   self.signals.done.emit({'message':f'{state} · {len(changes)} item(s)','changes':changes})
  except Exception as e:self.signals.failed.emit(str(e))
class SearchWorker(QRunnable):
 def __init__(self,base,term,content=False,hidden=False,generation=0):
  super().__init__(); self.base=Path(base); self.term=term; self.content=content; self.hidden=hidden; self.generation=generation; self.signals=WorkerSignals(); self.cancelled=False
 def cancel(self):self.cancelled=True
 def run(self):
  paths=[]
  try:
   if self.content:
    exe=shutil.which('rg')
    if not exe:raise RuntimeError('ripgrep is required for content search.')
    args=[exe,'-l','--no-messages','--max-count','1']+(['--hidden'] if self.hidden else [])+['--',self.term,str(self.base)]
   else:
    exe=shutil.which('fd') or shutil.which('fdfind')
    args=([exe,'--color','never','--max-results','2000']+(['--hidden'] if self.hidden else [])+['--',self.term,str(self.base)]) if exe else None
   if args:
    proc=subprocess.Popen(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    for line in proc.stdout:
     if self.cancelled:proc.terminate(); break
     raw=line.rstrip('\n');
     if raw:
      paths.append(raw); self.signals.progress.emit(len(paths),2000,raw)
     if len(paths)>=2000:proc.terminate(); break
    proc.wait(timeout=2)
   else:
    needle=self.term.casefold()
    for root,dirs,files in os.walk(self.base):
     if self.cancelled:break
     if not self.hidden:dirs[:]=[d for d in dirs if not d.startswith('.')]
     for name in dirs+files:
      if needle in name.casefold():
       raw=str(Path(root)/name); paths.append(raw); self.signals.progress.emit(len(paths),2000,raw)
       if len(paths)>=2000:break
     if len(paths)>=2000:break
   self.signals.done.emit({'generation':self.generation,'paths':paths,'cancelled':self.cancelled})
  except Exception as e:self.signals.failed.emit(str(e))

class Filter(QSortFilterProxyModel):
 def data(self,index,role=Qt.ItemDataRole.DisplayRole):
  if role==Qt.ItemDataRole.DisplayRole and index.column()==3:
   try:
    src=self.mapToSource(index); info=self.sourceModel().fileInfo(src); dt=info.lastModified()
    owner=self.parent().owner; fmt=getattr(owner,'date_format','Swedish')
    if fmt=='Swedish':return dt.toString('yyyy-MM-dd HH:mm')
    if fmt=='ISO':return dt.toString('yyyy-MM-ddTHH:mm:ss')
    if fmt=='Compact':return dt.toString('yy-MM-dd HH:mm')
   except Exception:pass
  return super().data(index,role)
 def filterAcceptsRow(self,row,parent):
  pat=self.filterRegularExpression().pattern()
  if not pat:return True
  idx=self.sourceModel().index(row,0,parent); return self.filterRegularExpression().match(self.sourceModel().fileName(idx)).hasMatch()
class BrowserTree(QTreeView):
 MIME='application/x-niruorg-files'
 def __init__(self,pane):
  super().__init__(pane); self.pane=pane; self.setAcceptDrops(True); self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop); self.setDefaultDropAction(Qt.DropAction.CopyAction); self.setDropIndicatorShown(True)
 def startDrag(self,supported):
  # QFileSystemModel's platform drag implementation is not reliable for FUSE
  # paths on Wayland. Publish explicit file URLs plus NIRUORG pane identity.
  paths=self.pane.selected()
  if not paths:return
  mime=QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
  side='left' if self.pane is self.pane.owner.pane1 else 'right'
  mime.setData(self.MIME,json.dumps({'source':side,'paths':[str(p) for p in paths]}).encode('utf-8'))
  drag=QDrag(self); drag.setMimeData(mime); drag.exec(Qt.DropAction.CopyAction,Qt.DropAction.CopyAction)
 def dragEnterEvent(self,event):
  if event.mimeData().hasUrls() or event.mimeData().hasFormat(self.MIME):event.acceptProposedAction()
  else:super().dragEnterEvent(event)
 def dragMoveEvent(self,event):
  if event.mimeData().hasUrls() or event.mimeData().hasFormat(self.MIME):event.acceptProposedAction()
  else:super().dragMoveEvent(event)
 def _drop_target(self,event):
  # Dropping on a directory copies into it; dropping on empty space or a file
  # copies into the pane's current directory. QFileSystemModel is queried only
  # for the already-visible index, avoiding extra remote filesystem probes.
  try:
   idx=self.indexAt(event.position().toPoint())
   if idx.isValid():
    src=self.pane.proxy.mapToSource(idx)
    if self.pane.model.isDir(src):return Path(self.pane.model.filePath(src))
  except Exception:pass
  return self.pane.current
 def dropEvent(self,event):
  mime=event.mimeData(); source=None; paths=[]
  if mime.hasFormat(self.MIME):
   try:
    payload=json.loads(bytes(mime.data(self.MIME)).decode('utf-8')); side=payload.get('source')
    source=self.pane.owner.pane1 if side=='left' else self.pane.owner.pane2 if side=='right' else None
    paths=[Path(x) for x in payload.get('paths',[]) if x]
   except Exception:paths=[]
  if not paths and mime.hasUrls():paths=[Path(u.toLocalFile()) for u in mime.urls() if u.isLocalFile()]
  if paths and source is not self.pane:
   # Finish the native Wayland drag transaction before opening any dialog or
   # starting transfer UI. A nested modal dialog from inside dropEvent can keep
   # the compositor's drag grab active, making the dialog appear but not accept
   # mouse/keyboard input. Snapshot everything now and defer NIRUORG handling.
   owner=self.pane.owner; dst=self.pane; items=list(paths); source_pane=source; target=self._drop_target(event)
   event.setDropAction(Qt.DropAction.CopyAction); event.accept()
   QTimer.singleShot(0,lambda o=owner,d=dst,x=items,sp=source_pane,t=target:o.handle_pane_drop(d,x,Qt.DropAction.CopyAction,sp,t))
   return
  super().dropEvent(event)
 def focusInEvent(self,event):
  self.pane.owner.set_active(self.pane); super().focusInEvent(event)
 def keyPressEvent(self,event):
  # File-browser keys are handled at the widget that actually receives them.
  # This avoids QAction/QShortcut ambiguity and behaves the same on Wayland/X11.
  owner=self.pane.owner
  action=owner._dispatch_browser_key(event.key(),event.modifiers(),self.pane,execute=False)
  if action:
   event.accept(); owner._trigger_browser_action(action,self.pane); return
  super().keyPressEvent(event)

class PaneTabBar(QTabBar):
 MIME='application/x-niruorg-pane-tab'
 def __init__(self,pane):
  super().__init__(pane); self.pane=pane; self._drag_start=None
  self.setAcceptDrops(True); self.setMouseTracking(True); self.tabMoved.connect(self._moved); self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.customContextMenuRequested.connect(self._menu)
 def mousePressEvent(self,e):
  self.pane.owner.set_active(self.pane)
  if e.button()==Qt.MouseButton.MiddleButton:
   i=self.tabAt(e.position().toPoint())
   if i>=0:self.pane.close_tab(i)
   e.accept(); return
  if e.button()==Qt.MouseButton.LeftButton:self._drag_start=e.position().toPoint()
  super().mousePressEvent(e)
 def mouseDoubleClickEvent(self,e):
  if e.button()==Qt.MouseButton.LeftButton and self.tabAt(e.position().toPoint())<0:
   self.pane.new_tab(); e.accept(); return
  super().mouseDoubleClickEvent(e)
 def mouseMoveEvent(self,e):
  super().mouseMoveEvent(e)
 def mouseReleaseEvent(self,e):
  super().mouseReleaseEvent(e)
  if e.button()!=Qt.MouseButton.LeftButton:return
  other=self.pane.owner.pane2 if self.pane is self.pane.owner.pane1 else self.pane.owner.pane1
  if not other.isVisible():return
  gp=e.globalPosition().toPoint(); lp=other.tabs.mapFromGlobal(gp)
  if other.tabs.rect().contains(lp):
   i=self.currentIndex()
   if i>=0:self.pane.copy_tab_to_other(i,True)
 def _moved(self,frm,to):
  if getattr(self.pane,'_tab_loading',False) or frm==to:return
  if 0<=frm<len(self.pane._tab_states) and 0<=to<len(self.pane._tab_states):
   st=self.pane._tab_states.pop(frm); self.pane._tab_states.insert(to,st); self.pane._sync_tab()
 def _menu(self,pos):
  i=self.tabAt(pos); m=QMenu(self)
  if i<0:
   m.addAction('New tab',lambda:self.pane.new_tab())
   a=m.addAction('Reopen closed tab',self.pane.reopen_closed_tab); a.setEnabled(bool(self.pane._closed_tabs))
   m.addSeparator(); m.addAction('Close other tabs',lambda:self.pane.close_other_tabs(self.pane.tabs.currentIndex())); m.addAction('Close all tabs',self.pane.close_all_tabs)
  else:
   self.setCurrentIndex(i); self.pane.owner.set_active(self.pane)
   m.addAction('New tab',lambda:self.pane.new_tab()); m.addAction('Duplicate tab',lambda:self.pane.duplicate_tab(i)); m.addSeparator()
   m.addAction('Open in other pane',lambda:self.pane.copy_tab_to_other(i,False)); m.addAction('Move tab to other pane',lambda:self.pane.copy_tab_to_other(i,True)); m.addSeparator()
   pinned=bool(self.pane._tab_states[i].get('pinned')) if i<len(self.pane._tab_states) else False
   m.addAction('Unpin tab' if pinned else 'Pin tab',lambda:self.pane.toggle_pin(i)); m.addSeparator()
   m.addAction('Close tab',lambda:self.pane.close_tab(i)); m.addAction('Close other tabs',lambda:self.pane.close_other_tabs(i)); m.addAction('Close tabs to the right',lambda:self.pane.close_tabs_right(i))
  m.exec(self.mapToGlobal(pos))

class FilePane(QWidget):
 def __init__(self,owner):
  super().__init__(); self.owner=owner; self.setObjectName('filePane'); self.setProperty('activePane',False); self.current=Path.home(); self.remote_name=None; self.remote_protocol=None; self.remote_mount=None; self.remote_root=None; self.model=QFileSystemModel(self); self.icons=SemanticIconProvider(owner.palette()); self.model.setIconProvider(self.icons); self.model.setFilter(QDir.Filter.AllEntries|QDir.Filter.NoDotAndDotDot|QDir.Filter.AllDirs)
  self.proxy=Filter(self); self.proxy.setSourceModel(self.model); self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
  self.view=BrowserTree(self); self.view.setModel(self.proxy); self.view.setSortingEnabled(True); self.view.sortByColumn(0,Qt.SortOrder.AscendingOrder); self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self.view.setUniformRowHeights(True); self.view.setAnimated(False); self.view.setIndentation(14); self.view.setRootIsDecorated(False); self.view.header().setStretchLastSection(False); self.view.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch); self.view.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents); self.view.header().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents); self.view.header().setSectionResizeMode(3,QHeaderView.ResizeMode.ResizeToContents); self.view.setDragEnabled(True); self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.view.customContextMenuRequested.connect(lambda p:owner.context_menu(self,p)); self.view.doubleClicked.connect(self.activate); self.view.clicked.connect(lambda *_:owner.set_active(self)); self.view.selectionModel().selectionChanged.connect(lambda *_:(owner.update_status(),owner.update_quicklook()))
  self.path=QLineEdit(); self.path.returnPressed.connect(self.commit_location); self.path.hide(); self.crumb=QWidget(); self.crumb_lay=QHBoxLayout(self.crumb); self.crumb_lay.setContentsMargins(0,0,0,0); self.crumb_lay.setSpacing(1); self.filter=QLineEdit(); self.filter.setPlaceholderText('Filter'); self.filter.setMaximumWidth(160); self.filter.textChanged.connect(self.set_filter)
  self.backb=QToolButton(); self.backb.setText('‹'); self.backb.setToolTip('Back'); self.backb.clicked.connect(self.back); self.upb=QToolButton(); self.upb.setText('↑'); self.upb.setToolTip('Parent folder'); self.upb.clicked.connect(self.up); self.close_split=QToolButton(); self.close_split.setText('×'); self.close_split.setToolTip('Close split view (Ctrl+2)'); self.close_split.clicked.connect(lambda:owner.close_split(self)); self.close_split.hide()
  self.tabs=PaneTabBar(self); self.tabs.setObjectName('paneTabs'); self.tabs.setDocumentMode(True); self.tabs.setMovable(True); self.tabs.setTabsClosable(False); self.tabs.setExpanding(False); self.tabs.setElideMode(Qt.TextElideMode.ElideRight); self.tabs.setUsesScrollButtons(True); self._tab_loading=False; self._tab_states=[]; self._closed_tabs=[]; self.tabs.currentChanged.connect(self._switch_tab); self.tabs.tabCloseRequested.connect(self.close_tab); self.tabs.tabBarClicked.connect(lambda *_:self.owner.set_active(self)); self.tabs.addTab('Home'); self._tab_states.append({}); self.tabs.setTabToolTip(0,str(Path.home())); self._install_tab_close(0)
  self.location_stack=QStackedWidget(); self.location_stack.addWidget(self.crumb); self.location_stack.addWidget(self.path)
  top=QHBoxLayout(); top.setContentsMargins(10,8,10,7); top.addWidget(self.backb); top.addWidget(self.upb); top.addWidget(self.location_stack,1); top.addWidget(self.filter); top.addWidget(self.close_split)
  self.history=[]; self.hist=-1
  for w in (self.path,self.filter,self.backb,self.upb,self.location_stack):w.installEventFilter(self)
  lay=QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0); lay.addWidget(self.tabs); lay.addLayout(top); lay.addWidget(self.view,1)
 def eventFilter(self,obj,event):
  if event.type() in (QEvent.Type.FocusIn,QEvent.Type.MouseButtonPress):self.owner.set_active(self)
  return super().eventFilter(obj,event)
 def _tab_state(self):
  return {'path':str(self.current),'remote_name':self.remote_name,'remote_protocol':self.remote_protocol,'remote_mount':str(self.remote_mount) if self.remote_mount else '','remote_root':self.remote_root or '/','history':list(self.history),'hist':self.hist,'filter':self.filter.text(),'pinned':bool(self._tab_states[self.tabs.currentIndex()].get('pinned')) if 0 <= self.tabs.currentIndex() < len(self._tab_states) else False}
 def _tab_title(self):
  current=self.current
  if os.path.normpath(str(current))==os.path.normpath(str(Path.home())):leaf='Home'
  elif str(current)=='/':leaf='/'
  else:leaf=current.name or str(current)
  return f'{self.remote_name} · {leaf}' if self.is_remote() else leaf
 def _install_tab_close(self,i):
  if i<0 or i>=self.tabs.count():return
  btn=QToolButton(self.tabs); btn.setObjectName('paneTabClose'); btn.setText('×'); btn.setAutoRaise(True); btn.setFixedSize(18,18); btn.setToolTip('Close tab (Ctrl+W)')
  btn.clicked.connect(lambda _=False,b=btn:self.close_tab(self.tabs.tabAt(b.pos())))
  self.tabs.setTabButton(i,QTabBar.ButtonPosition.RightSide,btn)
 def _sync_tab(self):
  if self._tab_loading or self.tabs.count()==0:return
  i=self.tabs.currentIndex()
  if i<0:return
  while len(self._tab_states)<self.tabs.count():self._tab_states.append({})
  self._tab_states[i]=self._tab_state(); title=self._tab_title()
  self.tabs.setTabText(i,('◆ ' if self._tab_states[i].get('pinned') else '')+title); self.tabs.setTabToolTip(i,(self.remote_name+':' if self.is_remote() else '')+self.display_path())
 def new_tab(self,path=None):
  self._sync_tab(); state=self._tab_state(); state['path']=str(path or self.current); i=self.tabs.addTab('New tab'); self._tab_states.append(state); self._install_tab_close(i); self.tabs.setCurrentIndex(i); self.owner.set_active(self)
 def _insert_tab_state(self,state,index=None,select=True):
  state=dict(state or {}); index=self.tabs.count() if index is None else max(0,min(index,self.tabs.count()))
  self._tab_loading=True
  try:
   self._tab_states.insert(index,state); self.tabs.insertTab(index,'Tab'); self._install_tab_close(index)
  finally:self._tab_loading=False
  if select:self.tabs.setCurrentIndex(index); self._switch_tab(index)
  else:self._refresh_tab_labels()
  return index
 def _refresh_tab_labels(self):
  cur=self.tabs.currentIndex()
  for i,st in enumerate(self._tab_states):
   path=Path(st.get('path',str(Path.home()))); leaf='Home' if path==Path.home() else ('/' if str(path)=='/' else (path.name or str(path)))
   title=f"{st.get('remote_name')} · {leaf}" if st.get('remote_name') else leaf
   if st.get('pinned'):title='◆ '+title
   self.tabs.setTabText(i,title); self.tabs.setTabToolTip(i,(str(st.get('remote_name'))+':' if st.get('remote_name') else '')+str(st.get('path','')))
  if cur>=0:self.tabs.setCurrentIndex(min(cur,self.tabs.count()-1))
 def close_tab(self,i,force=False):
  if i<0 or i>=self.tabs.count():return
  self._sync_tab()
  if self._tab_states[i].get('pinned') and not force:
   self.owner.status.setText('Pinned tab · unpin it before closing'); return
  closed=dict(self._tab_states[i]); closed['_origin_pane']=self.owner.pane_side(self)
  self._closed_tabs.insert(0,dict(closed)); self._closed_tabs=self._closed_tabs[:20]
  self.owner.closed_tabs_global.insert(0,dict(closed)); self.owner.closed_tabs_global=self.owner.closed_tabs_global[:30]
  self._tab_loading=True
  try:
   self._tab_states.pop(i); self.tabs.removeTab(i)
   if self.tabs.count()==0 and self is self.owner.pane1:
    self._tab_states.append({'path':str(Path.home()),'history':[],'hist':-1,'pinned':False}); self.tabs.addTab('Home'); self._install_tab_close(0)
  finally:self._tab_loading=False
  if self.tabs.count():self._switch_tab(max(0,self.tabs.currentIndex()))
  elif self is self.owner.pane2:self.owner._right_tabs_exhausted()
 def reopen_closed_tab(self):
  # Global history preserves the pane a tab came from. This makes Ctrl+Shift+T
  # restore a closed right pane instead of reopening its tab on the left.
  if self.owner.closed_tabs_global:
   st=dict(self.owner.closed_tabs_global.pop(0)); origin=st.pop('_origin_pane','left')
   target=self.owner.pane2 if origin=='right' else self.owner.pane1
   if target is self.owner.pane2:self.owner._show_right_pane(empty=True)
   target._insert_tab_state(st); self.owner.set_active(target); return
  if self._closed_tabs:
   st=dict(self._closed_tabs.pop(0)); st.pop('_origin_pane',None); self._insert_tab_state(st)
 def duplicate_tab(self,i):
  self._sync_tab()
  if 0<=i<len(self._tab_states):
   st=dict(self._tab_states[i]); st['pinned']=False; self._insert_tab_state(st,i+1)
 def toggle_pin(self,i):
  self._sync_tab()
  if 0<=i<len(self._tab_states):self._tab_states[i]['pinned']=not bool(self._tab_states[i].get('pinned')); self._refresh_tab_labels()
 def close_other_tabs(self,keep):
  self._sync_tab()
  for i in range(self.tabs.count()-1,-1,-1):
   if i!=keep and not self._tab_states[i].get('pinned'):self.close_tab(i,True)
 def close_tabs_right(self,i):
  self._sync_tab()
  for n in range(self.tabs.count()-1,i,-1):
   if not self._tab_states[n].get('pinned'):self.close_tab(n,True)
 def close_all_tabs(self):
  self._sync_tab()
  for i in range(self.tabs.count()-1,-1,-1):
   if not self._tab_states[i].get('pinned'):self.close_tab(i,True)
 def copy_tab_to_other(self,i,move=False):
  self._sync_tab()
  if not (0<=i<len(self._tab_states)):return
  target=self.owner.other_pane(self,True); target._insert_tab_state(dict(self._tab_states[i])); self.owner.set_active(target)
  if move:self.close_tab(i,True)
 def next_tab(self,delta=1):
  if self.tabs.count()>1:self.tabs.setCurrentIndex((self.tabs.currentIndex()+delta)%self.tabs.count())
 def export_tabs(self):
  self._sync_tab(); return [dict(x) for x in self._tab_states]
 def restore_tabs(self,states):
  if states is None:return
  self._tab_loading=True
  try:
   while self.tabs.count():self.tabs.removeTab(0)
   self._tab_states=[dict(x) for x in states]
   for _ in states:
    i=self.tabs.addTab('Tab'); self._install_tab_close(i)
   self.tabs.setCurrentIndex(0)
  finally:self._tab_loading=False
  self._switch_tab(0)
 def _switch_tab(self,i):
  if i<0 or i>=len(self._tab_states):return
  if self._tab_loading:return
  st=self._tab_states[i]
  if not st:return
  self._tab_loading=True
  try:
   if st.get('remote_name'):self.bind_remote(st['remote_name'],st.get('remote_protocol','SFTP'),st.get('remote_mount',''),st.get('remote_root','/'))
   else:self.clear_remote()
   self.history=list(st.get('history',[])); self.hist=int(st.get('hist',-1)); self.filter.setText(st.get('filter','')); self.go(st.get('path',str(Path.home())),False,leave_remote=not bool(st.get('remote_name'))); self.owner.set_active(self)
  finally:self._tab_loading=False
  self._sync_tab()
 def bind_remote(self,name,protocol,mount,remote_root='/'):
  self.remote_name=str(name); self.remote_protocol=str(protocol).upper(); self.remote_mount=Path(os.path.abspath(os.path.expanduser(str(mount)))); self.remote_root=str(remote_root or '/')
 def clear_remote(self):
  self.remote_name=None; self.remote_protocol=None; self.remote_mount=None; self.remote_root=None
 def is_remote(self):
  return bool(self.remote_name and self.remote_mount)
 def endpoint_label(self):
  base=f'REMOTE · {self.remote_name} · {self.remote_protocol}' if self.is_remote() else f'LOCAL · {socket.gethostname()}'
  active=self.owner.active is self
  return ('● ' if active else '  ')+base
 def side_name(self):
  return 'left' if self is self.owner.pane1 else 'right'

 def _path_inside_remote(self,p):
  if not self.remote_mount:return False
  try:return p==self.remote_mount or self.remote_mount in p.parents
  except Exception:return False
 def display_path(self):
  if not self.is_remote() or not self._path_inside_remote(self.current):return str(self.current)
  try:
   rel=self.current.relative_to(self.remote_mount)
   logical=Path(self.remote_root or '/').joinpath(rel)
   return '/' + str(logical).lstrip('/')
  except Exception:return str(self.remote_root or '/')

 def edit_location(self):
  self.path.setText(str(self.current)); self.location_stack.setCurrentWidget(self.path); self.path.setFocus(); self.path.selectAll()
 def commit_location(self):
  value=self.path.text(); self.location_stack.setCurrentWidget(self.crumb); self.go(value)
 def update_breadcrumbs(self):
  while self.crumb_lay.count():
   item=self.crumb_lay.takeAt(0); w=item.widget()
   if w:w.deleteLater()
  if self.is_remote():
   tag=QToolButton(); tag.setText(self.endpoint_label()); tag.setToolTip(f'Remote connection · {self.remote_name}'); tag.setEnabled(False); self.crumb_lay.addWidget(tag)
   sep=QLabel('›'); sep.setObjectName('crumbsep'); self.crumb_lay.addWidget(sep); remote_path=QLabel(self.display_path()); remote_path.setToolTip('Remote path'); self.crumb_lay.addWidget(remote_path); self.crumb_lay.addStretch(1); return
  tag=QToolButton(); tag.setText(self.endpoint_label()); tag.setToolTip('Local machine'); tag.setEnabled(False); self.crumb_lay.addWidget(tag)
  sep=QLabel('›'); sep.setObjectName('crumbsep'); self.crumb_lay.addWidget(sep)
  p=self.current; parts=list(p.parts); acc=Path(parts[0]) if parts else Path('/')
  for idx,part in enumerate(parts):
   if idx:acc=acc/part
   label='/' if idx==0 and part=='/' else (part or '/')
   b=QToolButton(); b.setText(label); target=str(acc); b.clicked.connect(lambda checked=False,x=target:self.go(x)); b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); b.customContextMenuRequested.connect(lambda pos,x=target:self.owner.path_actions(x)); self.crumb_lay.addWidget(b)
   if idx<len(parts)-1:
    sep=QLabel('›'); sep.setObjectName('crumbsep'); self.crumb_lay.addWidget(sep)
  self.crumb_lay.addStretch(1)
 def set_filter(self,t):self.proxy.setFilterRegularExpression(QRegularExpression(QRegularExpression.escape(t),QRegularExpression.PatternOption.CaseInsensitiveOption))
 def _apply_root(self,path,attempt=0):
  # QFileSystemModel populates directories asynchronously. setRootPath() both
  # requests the directory and returns its source index; never use an invalid
  # QModelIndex as the view root because Qt then exposes the local filesystem /.
  src=self.model.setRootPath(str(path))
  if src.isValid():
   self.view.setRootIndex(self.proxy.mapFromSource(src)); return True
  if attempt<20:
   QTimer.singleShot(50,lambda p=Path(path),a=attempt+1:self._apply_root(p,a)); return False
  self.owner.err(f'Could not open folder in file pane:\n{path}'); return False
 def _commit_go(self,path,push=True,leave_remote=False,verified_remote=False):
  p=Path(os.path.abspath(os.path.expanduser(str(path))))
  if self.is_remote():
   if not self._path_inside_remote(p):
    if leave_remote:self.clear_remote()
    else:return self.owner.err(f'Remote navigation blocked.\n\n{self.remote_name} is confined to its mounted filesystem.')
  elif not verified_remote:
   # Local paths are deliberately the only paths synchronously validated here.
   if not p.exists() or not p.is_dir():return self.owner.err(f'Folder not found:\n{p}')
  self.view.clearSelection(); self.view.setCurrentIndex(QModelIndex()); self.current=p
  self._apply_root(self.current); self.path.setText(str(self.current)); self.location_stack.setCurrentWidget(self.crumb); self.update_breadcrumbs(); self.filter.clear(); self.view.clearSelection(); self.view.setCurrentIndex(QModelIndex())
  if push:
   self.history=self.history[:self.hist+1]; self.history.append(str(self.current)); self.hist=len(self.history)-1
  self.owner.set_active(self); self.owner.record_location(self.current); self._sync_tab(); self.owner.update_status()
 def go(self,path,push=True,leave_remote=False):
  p=Path(os.path.abspath(os.path.expanduser(str(path))))
  remote=self.owner._remote_definition_for_path(p)
  if self.is_remote() or remote:
   if remote and not self.is_remote():
    name,proto,mp,root=remote; self.bind_remote(name,proto,mp,root)
   return self.owner.navigate_remote_async(self,p,push,leave_remote)
  return self._commit_go(p,push,leave_remote,False)
 def up(self):
  if self.is_remote() and self.current==self.remote_mount:return
  if self.current.parent!=self.current:self.go(self.current.parent)
 def back(self):
  if self.hist>0:self.hist-=1; self.go(self.history[self.hist],False)
 def forward(self):
  if self.hist+1<len(self.history):self.hist+=1; self.go(self.history[self.hist],False)
 def selected(self):
  out=[]
  for i in self.view.selectionModel().selectedRows(0):out.append(Path(self.model.filePath(self.proxy.mapToSource(i))))
  return out
 def activate(self,idx):
  src=self.proxy.mapToSource(idx); p=Path(self.model.filePath(src)); self.go(p) if self.model.isDir(src) else self.owner.open_path(p)
class Prefs(QDialog):
 def __init__(self,w):
  super().__init__(w); self.w=w; self.old_theme=w.theme; self.old_density=w.density; self.setWindowTitle('NIRUORG Settings'); self.setMinimumWidth(540); f=QFormLayout(self); f.setContentsMargins(22,22,22,22); f.setSpacing(12)
  self.theme=QComboBox(); self.theme.addItems(['Follow Omarchy']+list(THEMES)+['System']); self.theme.setCurrentText(w.theme)
  self.term=QLineEdit(w.terminal); self.shell=QLineEdit(w.shell); self.confirm=QCheckBox('Require confirmation'); self.confirm.setChecked(w.confirm_delete); self.density=QComboBox(); self.density.addItems(['Compact','Normal','Relaxed']); self.density.setCurrentText(w.density); self.datefmt=QComboBox(); self.datefmt.addItems(['Swedish','ISO','Compact','System']); self.datefmt.setCurrentText(w.date_format); self.restore=QCheckBox('Restore folders and split view on startup'); self.restore.setChecked(w.restore_session)
  self.audio=QComboBox(); self.audio.addItems(['NIRU Player (MPV backend)','System default','MPV','VLC','cmus']); self.audio.setCurrentText(getattr(w,'audio_player','NIRU Player (MPV backend)'))
  f.addRow('Theme',self.theme); f.addRow('Density',self.density); f.addRow('Date & time',self.datefmt); f.addRow('Terminal',self.term); f.addRow('Shell',self.shell); f.addRow('Permanent delete',self.confirm); f.addRow('Session',self.restore); f.addRow('Audio playback',self.audio)
  integ=[]
  for label,cmd in [('MPV','mpv'),('LocalSend','localsend'),('fd','fd'),('ripgrep','rg'),('7-Zip','7z')]:integ.append(f'{label}: {"available" if shutil.which(cmd) or (cmd=="fd" and shutil.which("fdfind")) else "not installed"}')
  info=QLabel('Integrations\n'+'  ·  '.join(integ)); info.setWordWrap(True); f.addRow(info)
  hint=QLabel('Theme and density preview live. Cancel restores the previous appearance.'); hint.setObjectName('muted'); hint.setWordWrap(True); f.addRow(hint)
  b=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
  for button in b.buttons(): button.setIcon(QIcon())
  b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
  self.theme.currentTextChanged.connect(self.preview_theme); self.density.currentTextChanged.connect(self.preview_density)
 def preview_theme(self,v):self.w.theme=v; self.w.apply_theme(); self.w.refresh_views()
 def preview_density(self,v):self.w.density=v; self.w.apply_theme(); self.w.refresh_views()
 def reject(self):
  self.w.theme=self.old_theme; self.w.density=self.old_density; self.w.apply_theme(); self.w.refresh_views(); super().reject()
 def accept(self):
  self.w.theme=self.theme.currentText(); self.w.terminal=self.term.text().strip(); self.w.shell=self.shell.text().strip(); self.w.confirm_delete=self.confirm.isChecked(); self.w.density=self.density.currentText(); self.w.date_format=self.datefmt.currentText(); self.w.restore_session=self.restore.isChecked(); self.w.audio_player=self.audio.currentText(); self.w.save_settings(); self.w.apply_theme(); self.w.refresh_views(); super().accept()
class SidebarList(QListWidget):
 pathsDropped=Signal(list)
 def __init__(self,parent=None):
  super().__init__(parent); self.setAcceptDrops(True); self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly); self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.setTextElideMode(Qt.TextElideMode.ElideRight)
 def dragEnterEvent(self,e):
  urls=e.mimeData().urls() if e.mimeData().hasUrls() else []
  if any(u.isLocalFile() for u in urls):e.acceptProposedAction()
  else:super().dragEnterEvent(e)
 def dragMoveEvent(self,e):
  if e.mimeData().hasUrls():e.acceptProposedAction()
  else:super().dragMoveEvent(e)
 def dropEvent(self,e):
  paths=[u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()] if e.mimeData().hasUrls() else []
  if paths:self.pathsDropped.emit(paths); e.acceptProposedAction()
  else:super().dropEvent(e)
class WorkBasketList(QListWidget):
 pathsDropped=Signal(list)
 def __init__(self,parent=None):
  super().__init__(parent); self.setAcceptDrops(True); self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
 def dragEnterEvent(self,e):
  if e.mimeData().hasUrls() and any(u.isLocalFile() for u in e.mimeData().urls()):e.acceptProposedAction()
  else:super().dragEnterEvent(e)
 def dragMoveEvent(self,e):
  if e.mimeData().hasUrls():e.acceptProposedAction()
  else:super().dragMoveEvent(e)
 def dropEvent(self,e):
  paths=[u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()] if e.mimeData().hasUrls() else []
  if paths:self.pathsDropped.emit(paths); e.acceptProposedAction()
  else:super().dropEvent(e)
class Main(QMainWindow):
 def __init__(self,path=None):
  super().__init__(); self.startup_trace=StartupTrace(); self.startup_trace.mark('settings begin'); self.s=QSettings('NIRU','NIRUORG'); self.theme=self.s.value('theme','Follow Omarchy' if omarchy_palette() else 'Niru Noir'); self.terminal=self.s.value('terminal',shutil.which('kitty') or shutil.which('x-terminal-emulator') or ''); self.shell=self.s.value('shell',shutil.which('fish') or shutil.which('bash') or '/bin/sh'); self.confirm_delete=self.s.value('confirm_delete',True,type=bool); self.density=self.s.value('density','Normal'); self.date_format=self.s.value('date_format','Swedish'); self.restore_session=self.s.value('restore_session',True,type=bool); self.audio_player=self.s.value('audio_player','NIRU Player (MPV backend)'); self.active=None; self.clip=[]; self.cut_mode=False; self.threadpool=QThreadPool.globalInstance(); self.dropzone=self.s.value('work_basket',[],type=list) or []; self.operations=[]; self.undo_stack=[]; self.running_workers=[]; self._worker_refs={}; self._worker_seq=0; self._accept_worker_results=True; self.collapsed_sections=set(self.s.value('collapsed_sections',[],type=list) or []); self.recent_locations=self.s.value('recent_locations',[],type=list) or []; self.focus_mode=False; self.shortcut_hits={}; self.closed_tabs_global=[]; self._hidden_right_tabs=None; self._remote_probe_pool=QThreadPool(self); self._remote_probe_pool.setMaxThreadCount(2); self._remote_probe_seq=0; self._remote_probe_tokens={}; self._cloud_cache=[]; self._cloud_types={}; self._devices_cache=[]; self._owned_mounts={}; self._shutdown_done=False; self._mount_journal=Path.home()/'.local/state/niruorg/owned-mounts.json'; self._load_mount_journal()
  self.input_diag_path=Path.home()/'.local/state/niruorg/input-diagnostics.log'; self.input_diag_enabled=False
  self._private_ssh_agent_pid=None; self._private_ssh_agent_sock=None
  QApplication.instance().installEventFilter(self)
  self.setWindowTitle(f'{APP}'); self.setWindowIcon(QIcon(str(Path(__file__).resolve().parent.parent/'assets/niruorg.svg'))); self.resize(1180,760); self.setMinimumSize(760,460)
  self.sidebar=SidebarList(); self.sidebar.setFixedWidth(176); self.sidebar.itemClicked.connect(self.sidebar_clicked); self.sidebar.pathsDropped.connect(self.add_shortcuts); self.sidebar.customContextMenuRequested.connect(self.sidebar_context_menu); self.build_sidebar(); self.startup_trace.mark('cheap sidebar')
  self.pane1=FilePane(self); self.pane2=FilePane(self); self.pane2.hide(); self.active=self.pane1; self.pane1.setProperty('activePane',True); self._install_browser_shortcuts()
  self.split=QSplitter(); self.split.setObjectName('mainSplitter'); self.split.addWidget(self.pane1); self.split.addWidget(self.pane2); self.split.setChildrenCollapsible(False); self.split.setHandleWidth(7); self.split.setStretchFactor(0,1); self.split.setStretchFactor(1,1); self.split.splitterMoved.connect(self._remember_split_sizes)
  center=QWidget(); row=QHBoxLayout(center); row.setContentsMargins(0,0,0,0); row.setSpacing(0); row.addWidget(self.sidebar); row.addWidget(self.split,1)
  self.status=QLabel(); self.status.setObjectName('status'); self.status.setContentsMargins(12,6,12,8)
  self.transfer_bar=QWidget(); self.transfer_bar.setObjectName('transferBar'); tb=QHBoxLayout(self.transfer_bar); tb.setContentsMargins(12,7,8,7); tb.setSpacing(10)
  texts=QWidget(); tx=QVBoxLayout(texts); tx.setContentsMargins(0,0,0,0); tx.setSpacing(1); self.transfer_title=QLabel(); self.transfer_title.setObjectName('transferTitle'); self.transfer_detail=QLabel(); self.transfer_detail.setObjectName('muted'); tx.addWidget(self.transfer_title); tx.addWidget(self.transfer_detail)
  self.progress=QProgressBar(); self.progress.setTextVisible(False); self.progress.setFixedWidth(220); self.progress.setMaximumHeight(5); self.transfer_cancel=QToolButton(); self.transfer_cancel.setText('Cancel'); self.transfer_cancel.clicked.connect(self._cancel_visible_transfer); tb.addWidget(texts,1); tb.addWidget(self.progress); tb.addWidget(self.transfer_cancel); self.transfer_bar.hide()
  self._transfer_states={}; self._visible_transfer=None; self._close_after_transfers=False
  c=QWidget(); lay=QVBoxLayout(c); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0); lay.addWidget(center,1); lay.addWidget(self.transfer_bar); lay.addWidget(self.status); self.setCentralWidget(c)
  self.quicklook_requested=False; self.build_quicklook(); self.build_menu(); self.shortcuts(); self.apply_theme(); self._startup_requested_path=path; self._startup_show_marked=False; self.startup_trace.mark('main window built'); self.pane1._commit_go(Path.home(),True); QApplication.instance().aboutToQuit.connect(self._shutdown_remote_resources); QTimer.singleShot(0,self._post_show_startup)
 def showEvent(self,event):
  super().showEvent(event)
  if not getattr(self,'_startup_show_marked',False):self._startup_show_marked=True; self.startup_trace.mark('window shown')
 def sidebar_clicked(self,i):
  target=i.data(Qt.ItemDataRole.UserRole)
  if isinstance(target,str) and target.startswith('__section__:'):
   key=target.split(':',1)[1]
   if key in self.collapsed_sections:self.collapsed_sections.remove(key)
   else:self.collapsed_sections.add(key)
   self.s.setValue('collapsed_sections',sorted(self.collapsed_sections)); self.build_sidebar(); return
  if target=='__dropzone__':self.show_dropzone(); return
  if target=='__cloud_manager__':self.manage_clouds(); return
  if isinstance(target,str) and target.startswith('__cloud__:'):
   self.open_cloud(target.split(':',1)[1]); return
  if target=='__server_manager__':self.manage_servers(); return
  if isinstance(target,str) and target.startswith('__server__:'):
   self.open_server_named(target.split(':',1)[1]); return
  if target=='__collections__':self.open_collection(); return
  if isinstance(target,str) and target.startswith('__workspace__:'):
   self.open_workspace_named(target.split(':',1)[1]); return
  if target:self.open_sidebar_location(target,self.active)
 def _sidebar_section(self,key,label,entries,always=False):
  if not entries and not always:return
  collapsed=key in self.collapsed_sections
  head=QListWidgetItem(('›  ' if collapsed else '⌄  ')+label); head.setToolTip(('Expand ' if collapsed else 'Collapse ')+label.title()); font=head.font(); font.setBold(True); head.setFont(font); head.setData(Qt.ItemDataRole.UserRole,'__section__:'+key); head.setData(Qt.ItemDataRole.UserRole+2,'section'); self.sidebar.addItem(head)
  if collapsed:return
  for text,target,tip,kind in entries:
   it=QListWidgetItem(text); it.setData(Qt.ItemDataRole.UserRole,target)
   if tip:it.setToolTip(tip)
   if kind:it.setData(Qt.ItemDataRole.UserRole+1,kind)
   self.sidebar.addItem(it)
 def build_sidebar(self):
  # Sidebar rendering is metadata-only. Never stat saved paths or FUSE mounts here.
  self.sidebar.clear(); dz=QListWidgetItem(f'WORK BASKET · {len(self.dropzone)}'); dz.setToolTip('Persistent working set across folders and sessions'); dz.setData(Qt.ItemDataRole.UserRole,'__dropzone__'); self.sidebar.addItem(dz)
  for label,p in [('Home',Path.home()),('Desktop',Path.home()/'Desktop'),('Documents',Path.home()/'Documents'),('Downloads',Path.home()/'Downloads'),('Pictures',Path.home()/'Pictures'),('Music',Path.home()/'Music'),('Videos',Path.home()/'Videos')]:
   it=QListWidgetItem(label); it.setData(Qt.ItemDataRole.UserRole,str(p)); self.sidebar.addItem(it)
  shortcuts=self._json_setting('shortcuts_json'); entries=[]
  for n,v in shortcuts.items():
   path=v.get('path','') if isinstance(v,dict) else str(v)
   if path:entries.append(('↗  '+n,path,path+'\nUser shortcut','shortcut:'+n))
  self._sidebar_section('shortcuts','SHORTCUTS',entries,True)
  self._sidebar_section('cloud','CLOUD',self._cloud_sidebar_entries(),True)
  pins=self.s.value('pins',[],type=list) or []; self._sidebar_section('pins','PINS',[(Path(p).name or p,p,p,None) for p in pins])
  self._sidebar_section('devices','DEVICES',[(Path(p).name or p,p,p,None) for p in self._devices_cache[:20]])
  try:cols=json.loads(self.s.value('collections_json','{}') or '{}')
  except:cols={}
  self._sidebar_section('collections','COLLECTIONS',[(f'Collections · {len(cols)}','__collections__','Virtual file collections',None)] if cols else [])
  targets=self._json_setting('targets_json'); tentries=[]
  for n,v in sorted(targets.items()):
   path=v.get('path','') if isinstance(v,dict) else str(v); tentries.append((n,path or None,path,None))
  self._sidebar_section('targets','TARGETS',tentries)
  workspaces=self._json_setting('workspaces_json'); self._sidebar_section('workspaces','WORKSPACES',[(n,'__workspace__:'+n,'Saved workspace',None) for n in sorted(workspaces)])
  mounts=mounted_paths(); servers=self._json_setting('servers_json'); sentries=[]
  for n,v in sorted(servers.items()):
   safe=''.join(c if c.isalnum() or c in '-_.' else '_' for c in n); mp=Path.home()/'.local/share/niruorg/mounts'/safe; mounted=path_is_mounted(mp,mounts); proto=v.get('protocol','sftp').upper(); route={'tailscale':'Tailscale','tailscale-ssh':'Tailscale SSH'}.get(v.get('route','direct'),'Direct')
   status='Mounted · checking on open' if mounted else 'Disconnected · click to connect'; tip=f'{n}\n{proto} · {route}\n{v.get("user","")+"@" if v.get("user") else ""}{v.get("host","")}:{v.get("port",22)}\n{status}'
   sentries.append((('● ' if mounted else '○ ')+n,'__server__:'+n,tip,'server:'+n))
  sentries.append(('+  Add connection','__server_manager__','Add or manage remote connections','server-manager'))
  self._sidebar_section('servers','SERVERS',sentries,True)
 def add_shortcuts(self,paths):
  data=self._json_setting('shortcuts_json'); added=0
  existing={str(v.get('path','')) if isinstance(v,dict) else str(v) for v in data.values()}
  for raw in paths:
   p=Path(raw)
   if not p.is_dir() or str(p) in existing:continue
   base=p.name or str(p); name=base; n=2
   while name in data:name=f'{base} {n}'; n+=1
   data[name]={'path':str(p)}; existing.add(str(p)); added+=1
  if added:self._save_json('shortcuts_json',data); self.build_sidebar(); self.status.setText(f'Added {added} shortcut(s)')
 def add_current_shortcut(self):self.add_shortcuts([str(self.current_dir())])
 def add_selected_shortcut(self):
  dirs=[str(p) for p in self.selected() if p.is_dir()]
  if not dirs:return self.err('Select one or more folders to add as shortcuts.')
  self.add_shortcuts(dirs)
 def sidebar_context_menu(self,pos):
  it=self.sidebar.itemAt(pos)
  if not it:return
  kind=it.data(Qt.ItemDataRole.UserRole+1)
  if isinstance(kind,str) and kind.startswith('cloud:'):
   name=kind.split(':',1)[1]; target=it.data(Qt.ItemDataRole.UserRole)
   m=QMenu(self); op=m.addAction('Open'); other=m.addAction(self.open_other_label()); m.addSeparator()
   if name=='nextcloud':
    act=m.exec(self.sidebar.viewport().mapToGlobal(pos))
    if act==op:self.open_sidebar_location(target,self.active)
    elif act==other:self.open_sidebar_other(target)
    return
   un=m.addAction('Unmount'); manage=m.addAction('Manage cloud services…'); act=m.exec(self.sidebar.viewport().mapToGlobal(pos))
   if act==op:self.open_cloud(name,self.active)
   elif act==other:self.open_cloud(name,self.other_pane(self.active,True))
   elif act==un:self.unmount_cloud(name)
   elif act==manage:self.manage_clouds()
   return
  if kind=='cloud-manager':self.manage_clouds(); return
  if kind=='server-manager':self.manage_servers(); return
  if isinstance(kind,str) and kind.startswith('server:'):
   name=kind.split(':',1)[1]; data=self._json_setting('servers_json'); v=data.get(name,{})
   safe=''.join(c if c.isalnum() or c in '-_.' else '_' for c in name); mp=Path.home()/'.local/share/niruorg/mounts'/safe; mounted=path_is_mounted(mp); proto=v.get('protocol','sftp').lower()
   m=QMenu(self); op=m.addAction('Open' if mounted else 'Connect / Open'); other=m.addAction(self.open_other_label()); m.addSeparator(); ssh=m.addAction('Open SSH terminal') if proto=='sftp' else None; details=m.addAction('Connection details'); test=m.addAction('Test connection'); disc=m.addAction('Disconnect') if mounted else None; m.addSeparator(); edit=m.addAction('Edit…'); clone=m.addAction('Duplicate…'); remove=m.addAction('Remove…'); act=m.exec(self.sidebar.viewport().mapToGlobal(pos))
   if act==op:self.open_server_named(name)
   elif act==other:self.open_server_named(name,True)
   elif ssh is not None and act==ssh:self.manage_servers(name,'ssh')
   elif act==details:self.manage_servers(name,'details')
   elif act==test:self.manage_servers(name,'test')
   elif disc is not None and act==disc:self.manage_servers(name,'disconnect')
   elif act==edit:self.manage_servers(name,'edit')
   elif act==clone:self.manage_servers(name,'clone')
   elif act==remove:self.manage_servers(name,'remove')
   return
  target=it.data(Qt.ItemDataRole.UserRole)
  if target and not (isinstance(target,str) and target.startswith('__')):
   m=QMenu(self); op=m.addAction('Open'); other=m.addAction(self.open_other_label())
   rename=remove=None
   if isinstance(kind,str) and kind.startswith('shortcut:'):
    m.addSeparator(); rename=m.addAction('Rename shortcut…'); remove=m.addAction('Remove shortcut')
   act=m.exec(self.sidebar.viewport().mapToGlobal(pos))
   if act==op:self.open_sidebar_location(target,self.active); return
   if act==other:self.open_sidebar_other(target); return
   if not (isinstance(kind,str) and kind.startswith('shortcut:')):return
   old=kind.split(':',1)[1]; data=self._json_setting('shortcuts_json')
  else:return
  if act==remove:
   data.pop(old,None); self._save_json('shortcuts_json',data); self.build_sidebar()
  elif act==rename:
   new,ok=QInputDialog.getText(self,'Rename shortcut','Display name:',text=old)
   if ok and new.strip() and new.strip()!=old:
    val=data.pop(old,None); data[new.strip()]=val; self._save_json('shortcuts_json',data); self.build_sidebar()
 def manage_shortcuts(self):
  data=self._json_setting('shortcuts_json'); d=NiruDialog(self); d.setWindowTitle('Shortcuts'); d.resize(680,440); l=QVBoxLayout(d); w=QListWidget()
  def refresh():
   w.clear()
   for n,v in data.items():
    path=v.get('path','') if isinstance(v,dict) else str(v); it=QListWidgetItem(f'↗  {n}   ·   {path}'); it.setData(Qt.ItemDataRole.UserRole,n); w.addItem(it)
  refresh(); l.addWidget(QLabel('Your shortcuts are references only. Removing one never deletes the folder.\nTip: drag folders from the browser directly into the sidebar.')); l.addWidget(w,1); row=QHBoxLayout(); add=QPushButton('Add folder…'); rename=QPushButton('Rename'); remove=QPushButton('Remove shortcut'); row.addWidget(add); row.addWidget(rename); row.addWidget(remove); row.addStretch(); l.addLayout(row)
  def addone():
   path=QFileDialog.getExistingDirectory(d,'Add shortcut',str(self.current_dir()))
   if path:self.add_shortcuts([path]); data.clear(); data.update(self._json_setting('shortcuts_json')); refresh()
  def ren():
   it=w.currentItem()
   if not it:return
   old=it.data(Qt.ItemDataRole.UserRole); new,ok=QInputDialog.getText(d,'Rename shortcut','Display name:',text=old)
   if ok and new.strip() and new.strip()!=old:data[new.strip()]=data.pop(old); self._save_json('shortcuts_json',data); refresh(); self.build_sidebar()
  def rem():
   it=w.currentItem()
   if it:data.pop(it.data(Qt.ItemDataRole.UserRole),None); self._save_json('shortcuts_json',data); refresh(); self.build_sidebar()
  add.clicked.connect(addone); rename.clicked.connect(ren); remove.clicked.connect(rem); d.exec()
 def build_quicklook(self):
  self.quickdock=QDockWidget('Quick Look',self); self.quickdock.setObjectName('quicklook'); self.quickdock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea|Qt.DockWidgetArea.LeftDockWidgetArea); self.quickdock.setMinimumWidth(280)
  box=QWidget(); lay=QVBoxLayout(box); lay.setContentsMargins(14,14,14,14); self.quick_image=QLabel(); self.quick_image.setAlignment(Qt.AlignmentFlag.AlignCenter); self.quick_image.setMinimumHeight(120); self.quick_image.setMaximumHeight(260); self.quick_name=QLabel('No selection'); self.quick_name.setWordWrap(True); self.quick_meta=QLabel(''); self.quick_meta.setWordWrap(True); self.quick_meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); lay.addWidget(self.quick_image); lay.addWidget(self.quick_name); lay.addWidget(self.quick_meta); lay.addStretch(1); self.quickdock.setWidget(box); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.quickdock); self.quickdock.hide(); self.quickdock.visibilityChanged.connect(lambda *_:self.update_quicklook())
 def toggle_quicklook(self):
  self.quicklook_requested=not self.quicklook_requested; self.quickdock.setVisible(self.quicklook_requested); self.update_quicklook()
 def update_quicklook(self):
  if not hasattr(self,'quickdock') or not getattr(self,'quicklook_requested',False):return
  sel=self.selected(); self.quick_image.clear()
  if len(sel)!=1:self.quick_name.setText('No selection' if not sel else f'{len(sel)} items selected'); self.quick_meta.setText(''); return
  p=sel[0]; self.quick_name.setText(p.name or str(p))
  try:
   st=p.lstat(); mime=mimetypes.guess_type(p.name)[0] or ('Folder' if p.is_dir() else 'File'); lines=[str(p),f'Type: {mime}',f'Size: {"—" if p.is_dir() else human(st.st_size)}',f'Modified: {self.format_dt(st.st_mtime)}',f'Permissions: {stat.filemode(st.st_mode)}']
   if mime.startswith('image/') and st.st_size < 80*1024*1024:
    pix=QPixmap(str(p))
    if not pix.isNull():self.quick_image.setPixmap(pix.scaled(250,220,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation)); lines.append(f'Image: {pix.width()} × {pix.height()}')
   elif mime.startswith(('audio/','video/')):
    mi=self.media_info(p)
    if mi:lines.append(mi)
   elif p.is_file() and st.st_size <= 256*1024 and (mime.startswith('text/') or p.suffix.lower() in ('.md','.py','.js','.ts','.json','.toml','.yaml','.yml','.conf','.ini')):
    try:
     text=p.read_text(errors='replace')[:1200].strip(); lines.append('\n'+text)
    except:pass
   self.quick_meta.setText('\n'.join(lines))
  except Exception as e:self.quick_meta.setText(str(e))
 def save_settings(self):
  for k,v in [('theme',self.theme),('terminal',self.terminal),('shell',self.shell),('confirm_delete',self.confirm_delete),('density',self.density),('date_format',self.date_format),('restore_session',self.restore_session),('audio_player',self.audio_player)]:self.s.setValue(k,v)
 def palette(self):
  if self.theme=='Follow Omarchy':return omarchy_palette() or THEMES['Niru Noir']
  if self.theme=='System':return THEMES['Niru Noir']
  return THEMES.get(self.theme,THEMES['Niru Noir'])
 def apply_theme(self):
  t=self.palette(); pad={'Compact':3,'Normal':5,'Relaxed':8}.get(self.density,5)
  self.setStyleSheet(('''QWidget { background:%(bg)s;color:%(fg)s;font-size:13px;selection-background-color:%(sel)s;selection-color:%(fg)s;} QTreeView,QListWidget,QPlainTextEdit {background:%(bg)s;border:0;} QLineEdit,QComboBox {background:%(panel)s;color:%(fg)s;padding:7px 9px;border:1px solid %(border)s;border-radius:5px;} QLineEdit:focus,QComboBox:focus {border:1px solid %(accent)s;} QListWidget {background:%(panel)s;padding:7px;border-right:1px solid %(border)s;} QListWidget::item {padding:6px;border-radius:4px;} QListWidget::item:hover {background:%(surface)s;} QListWidget::item:selected {background:%(sel)s;color:%(fg)s;} QTreeView::item {padding:%(pad)spx 4px;} QTreeView::item:hover {background:%(surface)s;} QTreeView::item:selected {background:%(sel)s;color:%(fg)s;} QHeaderView::section {background:%(panel)s;color:%(muted)s;padding:6px;border:0;border-bottom:1px solid %(border)s;} QToolButton,QPushButton {background:transparent;color:%(fg)s;border:1px solid transparent;border-radius:5px;padding:6px 10px;} QToolButton:hover,QPushButton:hover {background:%(surface)s;border-color:%(border)s;} QPushButton:default,QPushButton:focus,QToolButton:focus {border:1px solid %(accent)s;} QPushButton {qproperty-iconSize:0px 0px;} QPushButton:pressed,QToolButton:pressed {background:%(sel)s;} QMenu {background:%(panel)s;border:1px solid %(border)s;padding:5px;} QMenu::item {padding:7px 24px;border-radius:4px;} QMenu::item:selected {background:%(sel)s;} QDialog {background:%(bg)s;} QCheckBox::indicator {width:15px;height:15px;border:1px solid %(border)s;border-radius:3px;background:%(panel)s;} QCheckBox::indicator:checked {background:%(surface)s;border:2px solid %(fg)s;} QWidget#filePane[activePane="true"] {border-top:2px solid %(fg)s;} QTabBar#paneTabs {border-bottom:1px solid %(border)s;} QTabBar#paneTabs::tab {min-width:72px;padding:6px 8px 6px 12px;color:%(muted)s;background:%(panel)s;border-right:1px solid %(border)s;} QTabBar#paneTabs::tab:selected {color:%(fg)s;background:%(surface)s;font-weight:600;border-bottom:2px solid %(fg)s;} QWidget#filePane[activePane="false"] QTabBar#paneTabs::tab:selected {color:%(fg)s;background:%(surface)s;font-weight:500;border-bottom:2px solid %(muted)s;} QTabBar#paneTabs[activePane="true"]::tab:selected {color:%(fg)s;background:%(sel)s;font-weight:700;border-bottom:2px solid %(fg)s;} QToolButton#paneTabClose {color:%(muted)s;background:transparent;border:0;border-radius:3px;padding:0;margin:0;} QToolButton#paneTabClose:hover {color:%(fg)s;background:%(sel)s;border:0;} QSplitter#mainSplitter::handle {background:transparent;width:7px;} QSplitter#mainSplitter::handle:horizontal {border-left:1px solid %(border)s;} QLabel#crumbsep {color:%(muted)s;padding:0 2px;} QProgressBar {background:%(bg)s;border:0;} QProgressBar::chunk {background:%(fg)s;} QLabel#muted {color:%(muted)s;} QLabel#status {color:%(muted)s;border-top:1px solid %(border)s;} QWidget#transferBar {background:%(panel)s;border-top:1px solid %(border)s;} QLabel#transferTitle {font-weight:600;} QWidget#transferBar QProgressBar {background:%(bg)s;border:1px solid %(border)s;border-radius:2px;} QWidget#transferBar QProgressBar::chunk {background:%(fg)s;} QScrollBar:vertical {background:%(bg)s;width:9px;margin:0;} QScrollBar::handle:vertical {background:%(border)s;min-height:24px;border-radius:4px;} QScrollBar::add-line,QScrollBar::sub-line {height:0;width:0;}''') % {**t,'pad':pad})
  for pane in (getattr(self,'pane1',None),getattr(self,'pane2',None)):
   if pane: pane.icons.set_palette(t); pane.model.setIconProvider(pane.icons)
 def addact(self,m,text,fn,sc=None,bind=True):
  a=QAction(text,self); a.triggered.connect(fn)
  if sc:
   # Browser-reserved keys are handled directly by the file view. Keep their
   # shortcut visible in menus without registering a competing QAction shortcut.
   if bind:
    a.setShortcut(QKeySequence(sc)); a.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
   else:
    a.setText(f'{text}\t{sc}')
  m.addAction(a); return a
 def build_menu(self):
  mb=self.menuBar(); f=mb.addMenu('File'); self.addact(f,'New…',self.quick_create,'Ctrl+N'); self.addact(f,'New folder',self.new_folder,'Ctrl+Shift+N'); self.addact(f,'Rename',self.rename,'F2',False); self.addact(f,'Copy',self.copy,'Ctrl+C'); self.addact(f,'Cut',self.cut,'Ctrl+X'); self.addact(f,'Paste',self.paste,'Ctrl+V'); self.addact(f,'Undo last transfer',self.undo_last,'Ctrl+Z'); f.addSeparator(); self.addact(f,'Move to Trash',self.trash,'Delete',False); self.addact(f,'Delete Permanently…',self.permanent_delete,'Shift+Delete',False); self.addact(f,'Properties',self.properties,'Alt+Return')
  v=mb.addMenu('View'); self.addact(v,'Toggle sidebar',lambda:self.sidebar.setVisible(not self.sidebar.isVisible()),'Tab'); self.addact(v,'Split view',self.toggle_split,'Ctrl+2'); self.addact(v,'New tab',lambda:self.active.new_tab(),'Ctrl+T'); self.addact(v,'Close tab',lambda:self.active.close_tab(self.active.tabs.currentIndex()),'Ctrl+W'); self.addact(v,'Reopen closed tab',lambda:self.active.reopen_closed_tab(),'Ctrl+Shift+T'); self.addact(v,'Next tab',lambda:self.active.next_tab(1),'Ctrl+Tab'); self.addact(v,'Previous tab',lambda:self.active.next_tab(-1),'Ctrl+Shift+Tab'); self.addact(v,'List view',lambda:self.set_view('list'),'Ctrl+1'); self.addact(v,'Gallery view',lambda:self.set_view('gallery'),'Ctrl+3'); self.addact(v,'Show hidden files',self.toggle_hidden,'Ctrl+H'); self.addact(v,'Preview / Inspector',self.preview,'Space',False); self.addact(v,'Quick Look panel',self.toggle_quicklook,'F3'); self.addact(v,'Slideshow',self.slideshow,'F11'); self.addact(v,'Smart view',self.smart_view,'Ctrl+4'); self.addact(v,'Context summary',self.context_summary,'Ctrl+I'); self.addact(v,'Storage view',self.storage_view); self.addact(v,'Permissions view',self.permissions_view); self.addact(v,'Focus browser',self.toggle_focus,'F10')
  g=mb.addMenu('Go'); self.addact(g,'Home',lambda:self.active.go(str(Path.home())),'Alt+Home'); self.addact(g,'Back',lambda:self.active.back(),'Alt+Left'); self.addact(g,'Forward',lambda:self.active.forward(),'Alt+Right'); self.addact(g,'Parent',lambda:self.active.up(),'Backspace',False); self.addact(g,'Refresh',self.refresh_current,'F5',False); self.addact(g,'Location',lambda:self.active.edit_location(),'Ctrl+L'); self.addact(g,'Jump…',self.jump,'Ctrl+P'); self.addact(g,'Add current folder as Shortcut',self.add_current_shortcut,'Ctrl+Shift+B'); self.addact(g,'Manage Shortcuts…',self.manage_shortcuts); self.addact(g,'Pin current folder',self.pin_current); self.addact(g,'Work Basket',self.show_dropzone,'Ctrl+D'); self.addact(g,'Locations',self.manage_targets); self.addact(g,'Workspaces',self.manage_workspaces); self.addact(g,'Servers',self.manage_servers); self.addact(g,'Import connections…',self.import_connections); self.addact(g,'Cloud services…',self.manage_clouds)
  a=mb.addMenu('Actions'); self.addact(a,'Actions…',self.actions,'Ctrl+K'); self.addact(a,'Open With…',self.open_with,'Ctrl+Shift+O'); self.addact(a,'Context Lens',self.context_lens,'Ctrl+Shift+I'); self.addact(a,'Open terminal here',self.terminal_here,'Ctrl+Alt+T'); self.addact(a,'Play audio',self.play_audio,'Ctrl+Shift+P'); self.addact(a,'Play with MPV',self.mpv); self.addact(a,'Send with LocalSend',self.localsend); self.addact(a,'Browse archive…',self.archive_browser); self.addact(a,'Inspect package…',self.package_inspector); self.addact(a,'Extract here',self.extract); self.addact(a,'Compress to ZIP',self.compress); self.addact(a,'Calculate checksum',self.checksum); self.addact(a,'Copy path',self.copy_path,'Ctrl+Shift+C'); self.addact(a,'Copy shell-quoted path',self.copy_shell_path); self.addact(a,'Bulk rename',self.bulk_rename); self.addact(a,'Clipboard inspector',self.clipboard_inspector,'Ctrl+Shift+V'); self.addact(a,'Folder health',self.folder_health); self.addact(a,'Find duplicates…',self.duplicate_finder); self.addact(a,'Saved searches…',self.saved_searches); self.addact(a,'NIRU Actions…',self.manage_niru_actions); self.addact(a,'Recipes…',self.manage_recipes); self.addact(a,'Operation queue',self.operation_queue,'Ctrl+Shift+Q'); self.addact(a,'Operation history',self.operation_history,'Ctrl+Shift+H'); a.addSeparator(); self.addact(a,'Add to Work Basket',self.add_dropzone); self.copy_other_action=self.addact(a,self.copy_other_label(),self.send_other_pane,'Ctrl+Shift+Right'); self.move_other_action=self.addact(a,self.move_other_label(),self.move_other_pane,'Ctrl+Alt+Right'); self.addact(a,'Compare panes',self.compare_panes,'Ctrl+Shift+M'); self.addact(a,'Temporary split…',self.temporary_split,'Ctrl+Alt+2'); self.addact(a,'Save selection as Collection',self.save_collection); self.addact(a,'Open Collection',self.open_collection); self.addact(a,'Send to Target…',self.send_target)
  s=mb.addMenu('Settings'); self.addact(s,'Preferences…',lambda:Prefs(self).exec()); self.addact(s,'Integrations…',self.integrations); self.addact(s,'File Associations…',self.file_associations)
  h=mb.addMenu('Help'); self.addact(h,'Keybindings',self.show_keybindings); h.addSeparator(); self.addact(h,'Input diagnostics…',self.input_diagnostics); self.addact(h,'System diagnostics…',self.system_diagnostics); h.addSeparator(); self.addact(h,'About NIRUORG',self.show_about)
 def shortcuts(self):
  QShortcut(QKeySequence('/'),self,activated=lambda:self.active.filter.setFocus()); QShortcut(QKeySequence('Ctrl+F'),self,activated=self.find_files); QShortcut(QKeySequence('Ctrl+A'),self,activated=lambda:self.active.view.selectAll()); QShortcut(QKeySequence('Escape'),self,activated=self.escape_action)
 def _install_browser_shortcuts(self):
  # BrowserTree.keyPressEvent owns browser-reserved keys directly.
  # Keep this method as a compatibility hook; no competing QShortcut objects.
  self.browser_shortcuts=[]
 def _trigger_browser_action(self,action,pane):
  # One execution path for keyboard dispatch. Context menus call the same
  # final operations (trash/permanent_delete) directly.
  self.active=pane
  self.shortcut_hits[action]=self.shortcut_hits.get(action,0)+1
  if getattr(self,'input_diag_enabled',False):
   try:
    self.input_diag_path.parent.mkdir(parents=True,exist_ok=True)
    with self.input_diag_path.open('a',encoding='utf-8') as f:f.write(f'dispatch action={action} pane={"1" if pane is self.pane1 else "2"}\n')
   except Exception:pass
  if action=='Shift+Delete':self.permanent_delete()
  elif action=='Delete':self.trash()
  elif action=='F2':self.rename()
  elif action=='F5':self.refresh_current()
  elif action=='Backspace':pane.up()
  elif action=='Return':self.open_selected()
  elif action=='Space':self.preview()
  return True
 def _focus_is_text_input(self):
  w=QApplication.focusWidget()
  return isinstance(w,(QLineEdit,QPlainTextEdit,QTextEdit,QSpinBox,QDoubleSpinBox,QComboBox))
 def _browser_has_focus(self):
  w=QApplication.focusWidget()
  if w is None:return False
  panes=(getattr(self,'pane1',None),getattr(self,'pane2',None))
  for pane in panes:
   if pane is not None and (w is pane.view or pane.view.isAncestorOf(w)):return True
  return False
 def _pane_for_event_target(self,obj):
  # QTreeView keyboard events may target the view itself or its viewport.
  # Resolve the owning pane from the actual receiver instead of relying on
  # whichever pane happened to be active previously.
  # eventFilter can run while QMainWindow is still being constructed, before
  # the file panes exist. Early Qt events must therefore be harmless.
  for pane in (getattr(self,'pane1',None),getattr(self,'pane2',None)):
   if pane is None:continue
   w=obj
   while w is not None:
    if w is pane.view:return pane
    try:w=w.parentWidget()
    except Exception:break
  return None
 def _normalized_modifiers(self,mods):
  # Ignore platform-specific modifier bits that are irrelevant to these file
  # operations, while preserving Ctrl/Alt/Meta so Shift+Delete is exact.
  mask=(Qt.KeyboardModifier.ShiftModifier|Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.AltModifier|Qt.KeyboardModifier.MetaModifier)
  return mods & mask
 def _dispatch_browser_key(self,key,mods,pane=None,execute=True):
  mods=self._normalized_modifiers(mods)
  action=None
  if key==Qt.Key.Key_Delete and mods==Qt.KeyboardModifier.ShiftModifier:action='Shift+Delete'
  elif key==Qt.Key.Key_Delete and mods==Qt.KeyboardModifier.NoModifier:action='Delete'
  elif key==Qt.Key.Key_F2 and mods==Qt.KeyboardModifier.NoModifier:action='F2'
  elif key==Qt.Key.Key_F5 and mods==Qt.KeyboardModifier.NoModifier:action='F5'
  elif key==Qt.Key.Key_Backspace and mods==Qt.KeyboardModifier.NoModifier:action='Backspace'
  elif key in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and mods==Qt.KeyboardModifier.NoModifier:action='Return'
  elif key==Qt.Key.Key_Space and mods==Qt.KeyboardModifier.NoModifier:action='Space'
  if not action:return False
  if not execute:return action
  return self._trigger_browser_action(action,pane or self.active)
 def _input_diag(self,obj,event,pane=None,matched=None):
  if not getattr(self,'input_diag_enabled',False):return
  if event.type() not in (QEvent.Type.ShortcutOverride,QEvent.Type.KeyPress,QEvent.Type.KeyRelease):return
  try:
   self.input_diag_path.parent.mkdir(parents=True,exist_ok=True)
   et={QEvent.Type.ShortcutOverride:'ShortcutOverride',QEvent.Type.KeyPress:'KeyPress',QEvent.Type.KeyRelease:'KeyRelease'}.get(event.type(),str(int(event.type())))
   mods=int(event.modifiers().value); key=int(event.key()); target=type(obj).__name__; pn='1' if pane is getattr(self,'pane1',None) else ('2' if pane is getattr(self,'pane2',None) else '-')
   with self.input_diag_path.open('a',encoding='utf-8') as f:f.write(f'{et} key={key} modifiers=0x{mods:x} target={target} pane={pn} matched={matched or "-"}\n')
  except Exception:pass
 def input_diagnostics(self):
  d=NiruDialog(self); d.setWindowTitle('Input diagnostics'); d.resize(720,500); l=QVBoxLayout(d); info=QLabel('Temporary keyboard diagnostics for the NIRUORG file browser.\nNo typed text is recorded; only Qt key codes, modifier flags, event type, target widget and pane.'); info.setWordWrap(True); l.addWidget(info)
  state=QLabel(); l.addWidget(state); out=QPlainTextEdit(); out.setReadOnly(True); l.addWidget(out,1)
  def refresh():
   state.setText('Recording: ON' if self.input_diag_enabled else 'Recording: OFF')
   try:out.setPlainText(self.input_diag_path.read_text(encoding='utf-8')[-20000:])
   except Exception:out.setPlainText('No diagnostic events recorded yet.')
  row=QHBoxLayout(); toggle=QPushButton('Start recording' if not self.input_diag_enabled else 'Stop recording'); clear=QPushButton('Clear log'); copy=QPushButton('Copy log'); refreshb=QPushButton('Refresh'); row.addWidget(toggle); row.addWidget(clear); row.addWidget(copy); row.addWidget(refreshb); row.addStretch(1); l.addLayout(row)
  def tog():
   self.input_diag_enabled=not self.input_diag_enabled; toggle.setText('Stop recording' if self.input_diag_enabled else 'Start recording'); refresh()
  def clr():
   try:self.input_diag_path.unlink(missing_ok=True)
   except Exception:pass
   refresh()
  toggle.clicked.connect(tog); clear.clicked.connect(clr); copy.clicked.connect(lambda:QApplication.clipboard().setText(out.toPlainText())); refreshb.clicked.connect(refresh); refresh(); d.exec()
 def eventFilter(self,obj,event):
  pane=self._pane_for_event_target(obj)
  if getattr(self,'input_diag_enabled',False) and event.type() in (QEvent.Type.ShortcutOverride,QEvent.Type.KeyPress,QEvent.Type.KeyRelease):
   self._input_diag(obj,event,pane,self._dispatch_browser_key(event.key(),event.modifiers(),pane,False) if pane is not None else None)
  # Do not consume browser key events here. View-owned QShortcuts are the
  # authoritative path; the application filter is diagnostics only.
  return super().eventFilter(obj,event)
 def keybinding_rows(self):
  return [
   ('Files','Ctrl+N','New file / folder'),('Files','Ctrl+Shift+N','New folder'),('Files','F2','Rename'),('Files','Ctrl+C','Copy'),('Files','Ctrl+X','Cut'),('Files','Ctrl+V','Paste'),('Files','Delete','Move to Trash'),('Files','Shift+Delete','Delete Permanently…'),('Files','Alt+Return','Properties'),('Files','Ctrl+A','Select all'),
   ('Navigation','Alt+Left','Back'),('Navigation','Alt+Right','Forward'),('Navigation','Backspace','Parent folder'),('Navigation','Alt+Home','Home'),('Navigation','Ctrl+L','Location'),('Navigation','Ctrl+P','Jump'),('Navigation','F5','Refresh'),
   ('Search','/','Filter current folder'),('Search','Ctrl+F','Find files / content'),('Actions','Ctrl+K','Command palette'),('Tabs','Ctrl+T','New tab'),('Tabs','Ctrl+W','Close tab'),('Tabs','Ctrl+Shift+T','Reopen closed tab'),('Actions','Ctrl+Alt+T','Open terminal here'),('Actions','Ctrl+Shift+C','Copy path'),('Actions','Ctrl+Shift+V','Clipboard inspector'),
   ('Views','Ctrl+1','List'),('Views','Ctrl+2','Split'),('Views','Ctrl+3','Gallery'),('Views','Ctrl+4','Smart view'),('Views','Space','Inspector'),('Views','F3','Quick Look'),('Views','F10','Focus browser'),('Views','F11','Slideshow'),('Views','Ctrl+H','Hidden files'),('Views','Tab','Sidebar'),
   ('Organizer','Ctrl+D','Work Basket'),('Organizer','Ctrl+Alt+2','Temporary split'),('Organizer','Ctrl+Shift+B','Shortcut current folder'),('Organizer','Ctrl+Shift+Right','Send to other pane'),('Organizer','Ctrl+Shift+M','Compare panes'),('Operations','Ctrl+Z','Undo transfer'),('Operations','Ctrl+Shift+Q','Operation queue'),('Operations','Ctrl+Shift+H','Operation history'),('Media','Ctrl+Shift+P','Play with MPV')]
 def show_keybindings(self):
  d=NiruDialog(self); d.setWindowTitle('NIRUORG Keybindings'); d.resize(720,620); l=QVBoxLayout(d); q=QLineEdit(); q.setPlaceholderText('Filter keybindings…'); tree=QTreeWidget(); tree.setHeaderLabels(['Category','Key','Action']); tree.setRootIsDecorated(False); l.addWidget(q); l.addWidget(tree,1)
  def fill(t=''):
   tree.clear(); needle=t.casefold().strip()
   for cat,key,desc in self.keybinding_rows():
    if needle and needle not in f'{cat} {key} {desc}'.casefold():continue
    QTreeWidgetItem(tree,[cat,key,desc])
   tree.header().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); tree.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents); tree.header().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
  q.textChanged.connect(fill); fill(); q.setFocus(); d.exec()
 def show_about(self):
  self.info_dialog('About NIRUORG',f'<b>NIRUORG {VERSION}</b><br><br>Minimal but powerful file organizer for Linux.<br>Fast local and remote file management with a keyboard-first workflow and full mouse support.<br><br>Created by Nicklas Rudolfsson.')
 def refresh_current(self):
  self.active.model.setRootPath(''); self.active.model.setRootPath(str(self.active.current)); self.active.go(self.active.current,False); self.update_status()
 def escape_action(self):
  if self.active.filter.hasFocus() or self.active.filter.text():self.active.filter.clear(); self.active.view.setFocus(); return
  self.active.view.clearSelection(); self.update_status()
 def quick_create(self):
  d=NiruDialog(self); d.setWindowTitle('New'); d.setMinimumWidth(420); f=QFormLayout(d); kind=QComboBox(); kind.addItems(['Text file','Markdown file','Folder']); name=QLineEdit(); name.setPlaceholderText('Name'); f.addRow('Type',kind); f.addRow('Name',name); b=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); [x.setIcon(QIcon()) for x in b.buttons()]; f.addRow(b); b.accepted.connect(d.accept); b.rejected.connect(d.reject); name.setFocus()
  if d.exec()!=QDialog.DialogCode.Accepted:return
  n=name.text().strip()
  if not n:return
  if kind.currentText()=='Markdown file' and not Path(n).suffix:n += '.md'
  target=self.current_dir()/n
  if target.exists():return self.err(f'Already exists: {target.name}')
  try:
   if kind.currentText()=='Folder':target.mkdir()
   else:target.touch(exist_ok=False)
   if target.suffix.lower()=='.md':self.open_path(target)
  except Exception as e:self.err(e)
 def set_active(self,p):
  self.active=p
  for pane in (self.pane1,self.pane2):
   pane.setProperty('activePane',pane is p); pane.tabs.setProperty('activePane',pane is p); pane.style().unpolish(pane); pane.style().polish(pane); pane.tabs.style().unpolish(pane.tabs); pane.tabs.style().polish(pane.tabs); pane.update_breadcrumbs()
  if hasattr(self,'copy_other_action') and self.copy_other_action:
   self.copy_other_action.setText(self.copy_other_label()); self.move_other_action.setText(self.move_other_label())
  self.update_status()
 def pane_side(self,pane):return 'left' if pane is self.pane1 else 'right'
 def other_side(self,pane=None):return 'right' if (pane or self.active) is self.pane1 else 'left'
 def open_other_label(self):return f'Open in {self.other_side()} pane'
 def copy_other_label(self):return f'Copy to {self.other_side()} pane'
 def move_other_label(self):return f'Move to {self.other_side()} pane…'
 def other_pane(self,pane=None,ensure=True):
  pane=pane or self.active
  if ensure and not self.pane2.isVisible():self.show_right_pane()
  return self.pane2 if pane is self.pane1 else self.pane1
 def open_sidebar_location(self,target,pane=None):
  pane=pane or self.active; pane.go(target,leave_remote=True); self.set_active(pane)
 def open_sidebar_other(self,target):
  pane=self.other_pane(self.active,True); self.open_sidebar_location(target,pane)
 def pane_target_label(self,pane):
  return f'{pane.endpoint_label()} · {pane.display_path()}'

 def selected(self):return self.active.selected()
 def current_dir(self):return self.active.current
 def update_status(self):
  s=self.selected(); extra=' · split' if self.pane2.isVisible() else ''; total=0
  for p in s:
   try:
    if p.is_file():total+=p.stat().st_size
   except OSError:pass
  label=(f'{len(s)} selected' + (f' · {human(total)}' if total else '')) if s else str(self.current_dir()); side=(f'{self.pane_side(self.active).capitalize()} active · ' if self.pane2.isVisible() else ''); self.status.setText(side+label+extra)
 def record_location(self,path):
  p=str(path)
  if p in self.recent_locations:self.recent_locations.remove(p)
  self.recent_locations.insert(0,p); self.recent_locations=self.recent_locations[:30]; self.s.setValue('recent_locations',self.recent_locations)
 def toggle_focus(self):
  self.focus_mode=not self.focus_mode; self.sidebar.setVisible(not self.focus_mode); self.menuBar().setVisible(not self.focus_mode); self.status.setVisible(not self.focus_mode); self.transfer_bar.setVisible(False if self.focus_mode else bool(self.operations));
  if self.focus_mode and hasattr(self,'quickdock'):self.quickdock.hide()
 def jump(self):
  entries=[]
  for label,p in [('Home',Path.home()),('Documents',Path.home()/'Documents'),('Downloads',Path.home()/'Downloads'),('Pictures',Path.home()/'Pictures'),('Music',Path.home()/'Music')]:
   if p.exists():entries.append((label,str(p),'Place'))
  for n,v in self._json_setting('shortcuts_json').items():entries.append((n,v.get('path','') if isinstance(v,dict) else str(v),'Shortcut'))
  for p in self.recent_locations:
   if Path(p).exists():entries.append((Path(p).name or p,p,'Recent'))
  for n in self._json_setting('workspaces_json'):entries.append((n,'__workspace__:'+n,'Workspace'))
  d=NiruDialog(self); d.setWindowTitle('Jump'); d.resize(620,460); l=QVBoxLayout(d); q=QLineEdit(); q.setPlaceholderText('Type to jump…'); w=QTreeWidget(); w.setHeaderLabels(['Name','Type','Location']); w.setRootIsDecorated(False); l.addWidget(q); l.addWidget(w,1)
  def fill(text=''):
   w.clear(); t=text.casefold().strip()
   for name,target,kind in entries:
    if t and t not in (name+' '+target+' '+kind).casefold():continue
    it=QTreeWidgetItem(w,[name,kind,target.replace('__workspace__:','')]); it.setData(0,Qt.ItemDataRole.UserRole,target)
   w.header().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); w.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents); w.header().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
  def go():
   it=w.currentItem()
   if not it:return
   target=it.data(0,Qt.ItemDataRole.UserRole); d.accept(); self.open_workspace_named(target.split(':',1)[1]) if str(target).startswith('__workspace__:') else self.active.go(target)
  q.textChanged.connect(fill); q.returnPressed.connect(go); w.itemDoubleClicked.connect(lambda *_:go()); fill(); q.setFocus(); d.exec()
 def format_dt(self,ts):
  from datetime import datetime
  d=datetime.fromtimestamp(ts)
  if self.date_format=='Swedish':return d.strftime('%Y-%m-%d %H:%M')
  if self.date_format=='ISO':return d.strftime('%Y-%m-%dT%H:%M:%S')
  if self.date_format=='Compact':return d.strftime('%y-%m-%d %H:%M')
  return d.strftime('%x %X')
 def refresh_views(self):
  for pane in (self.pane1,self.pane2):
   pane.proxy.invalidate(); pane.view.viewport().update(); pane.view.header().viewport().update()
 def smart_view(self):
  try: files=[p for p in self.current_dir().iterdir() if p.is_file()]
  except Exception as e:return self.err(e)
  if not files:return self.status.setText('Smart view · empty folder')
  images=[p for p in files if (mimetypes.guess_type(p.name)[0] or '').startswith('image/')]
  media=[p for p in files if (mimetypes.guess_type(p.name)[0] or '').startswith(('audio/','video/'))]
  if len(images)/len(files)>=0.5:return self.gallery()
  if len(media)/len(files)>=0.5:
   self.status.setText(f'Smart view · media folder · {len(media)} playable item(s) · Ctrl+P to play')
   return
  self.context_summary()
 def context_summary(self):
  try:
   items=list(self.current_dir().iterdir()); dirs=[p for p in items if p.is_dir()]; files=[p for p in items if p.is_file()]; total=sum(p.stat().st_size for p in files if p.exists()); groups={}
   for p in files:
    mime=mimetypes.guess_type(p.name)[0] or 'other'; kind=mime.split('/',1)[0] if '/' in mime else 'other'; groups[kind]=groups.get(kind,0)+1
   git=(self.current_dir()/'.git').exists(); docker=any((self.current_dir()/n).exists() for n in ('compose.yaml','compose.yml','docker-compose.yml')); py=any((self.current_dir()/n).exists() for n in ('pyproject.toml','requirements.txt')); node=(self.current_dir()/'package.json').exists()
   tags=[x for x,v in [('Git',git),('Docker',docker),('Python',py),('Node',node)] if v]; git_detail=''
   if git and shutil.which('git'):
    try:
     gr=subprocess.run(['git','status','--porcelain','--branch'],cwd=self.current_dir(),capture_output=True,text=True,timeout=3); gl=gr.stdout.splitlines(); git_detail=(gl[0].replace('## ','') if gl else '')+f' · {max(0,len(gl)-1)} changed'
    except Exception:pass
   lines=[str(self.current_dir()),'',f'{len(dirs)} folders · {len(files)} files · {human(total)} direct file size']+[f'{k}: {v}' for k,v in sorted(groups.items())]
   if tags:lines += ['', 'Project context: '+' · '.join(tags)]
   if git_detail:lines += ['Git: '+git_detail]
   self.info('Context summary','\n'.join(lines))
  except Exception as e:self.err(e)
 def storage_view(self):
  try:
   d=NiruDialog(self); d.setWindowTitle(f'Storage — {self.current_dir()}'); d.resize(760,520); l=QVBoxLayout(d)
   usage=shutil.disk_usage(self.current_dir()); head=QLabel(f'<b>{self.current_dir()}</b><br>{human(usage.used)} used · {human(usage.free)} free · {human(usage.total)} total'); l.addWidget(head)
   bar=QProgressBar(); bar.setRange(0,1000); bar.setValue(int(usage.used/usage.total*1000) if usage.total else 0); l.addWidget(bar)
   w=QTreeWidget(); w.setHeaderLabels(['Name','Type','Direct size']); w.setRootIsDecorated(False)
   for p in sorted(self.current_dir().iterdir(),key=lambda x:(not x.is_dir(),x.name.lower())):
    try:size='—' if p.is_dir() else human(p.stat().st_size)
    except:size='—'
    QTreeWidgetItem(w,[p.name,'Folder' if p.is_dir() else (mimetypes.guess_type(p.name)[0] or 'File'),size])
   w.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch); w.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents); w.header().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents); l.addWidget(w,1); l.addWidget(QLabel('Directory sizes are intentionally not calculated recursively. Use Inspector when needed.')); d.exec()
  except Exception as e:self.err(e)
 def permissions_view(self):
  try:
   d=NiruDialog(self); d.setWindowTitle(f'Permissions — {self.current_dir()}'); d.resize(850,560); l=QVBoxLayout(d); w=QTreeWidget(); w.setHeaderLabels(['Name','Mode','UID:GID','Writable','Type']); w.setRootIsDecorated(False)
   for p in sorted(self.current_dir().iterdir(),key=lambda x:x.name.lower()):
    try:
     st=p.lstat(); QTreeWidgetItem(w,[p.name,stat.filemode(st.st_mode),f'{st.st_uid}:{st.st_gid}','Yes' if os.access(p,os.W_OK) else 'No','Folder' if p.is_dir() else 'File'])
    except Exception:pass
   w.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
   for i in range(1,5):w.header().setSectionResizeMode(i,QHeaderView.ResizeMode.ResizeToContents)
   l.addWidget(QLabel('Read-only context view · no recursive permission scan.')); l.addWidget(w,1); d.exec()
  except Exception as e:self.err(e)
 def operation_queue(self):
  d=NiruDialog(self); d.setWindowTitle('Operation queue'); d.resize(720,430); l=QVBoxLayout(d); w=QTreeWidget(); w.setHeaderLabels(['State','Operation','Items','Destination']); w.setRootIsDecorated(False)
  running=list(self.operations)
  for x in running:QTreeWidgetItem(w,['Running','Move' if x.move else 'Copy',str(len(x.items)),str(x.dst)])
  for changes in reversed(self.undo_stack[-50:]):QTreeWidgetItem(w,['Done','Transfer',str(len(changes)),''])
  w.header().setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch); l.addWidget(QLabel('Transfers run outside the UI thread. Running operations can be cancelled between files.')); l.addWidget(w,1)
  cancel=QPushButton('Cancel running operations'); cancel.setEnabled(bool(running)); cancel.clicked.connect(lambda:[x.cancel() for x in running]); l.addWidget(cancel); d.exec()
 def operation_history(self):
  d=NiruDialog(self); d.setWindowTitle('Operation history'); d.resize(760,480); l=QVBoxLayout(d); w=QListWidget()
  if not self.undo_stack:w.addItem('No reversible transfer operations in this session.')
  else:
   for op in reversed(self.undo_stack):
    changes=op if isinstance(op,list) else op.get('changes',[]); verb='Move' if any(x.get('move') for x in changes) else 'Copy'; w.addItem(f'{verb} · {len(changes)} item(s)')
  l.addWidget(QLabel('Session history · only operations performed by NIRUORG are tracked.')); l.addWidget(w,1); b=QPushButton('Undo latest'); b.setEnabled(bool(self.undo_stack)); b.clicked.connect(lambda:(self.undo_last(),d.accept())); l.addWidget(b); d.exec()
 def context_menu(self,pane,pos):
  self.set_active(pane); m=QMenu(self); sel=self.selected(); one=sel[0] if len(sel)==1 else None; audio=bool(one and one.is_file() and one.suffix.lower() in {'.mp3','.flac','.ogg','.opus','.m4a','.aac','.wav','.wma','.ape'}); m.addAction('Open',self.open_selected); m.addAction('Open With…',self.open_with); m.addAction('Preview',self.preview); m.addSeparator(); m.addAction('Copy',self.copy); m.addAction('Cut',self.cut); m.addAction('Paste',self.paste); m.addAction(self.copy_other_label(),self.send_other_pane); m.addAction(self.move_other_label(),self.move_other_pane); m.addAction('Rename',self.rename); m.addAction('Move to Trash',self.trash); m.addAction('Delete Permanently…',self.permanent_delete); m.addSeparator(); m.addAction('Open terminal here',self.terminal_here);
  if audio:
   m.addAction('Play in NIRU Player',lambda:self.niru_player([one],0)); m.addAction('Play with configured player',self.play_audio);
   if shutil.which('mpv'):m.addAction('Play with MPV',self.mpv)
  m.addAction('Send with LocalSend',self.localsend); m.addAction('Add to Work Basket',self.add_dropzone); m.addAction('Run NIRU Action…',self.run_niru_action); m.addAction('Run Recipe…',self.run_recipe); m.addAction('Add folder as Shortcut',self.add_selected_shortcut);
  if self.pane2.isVisible():m.addAction('Send to other pane',self.send_other_pane)
  m.addAction('Extract here',self.extract); m.addAction('Compress to ZIP',self.compress); m.addSeparator(); m.addAction('Copy path',self.copy_path); m.addAction('Copy shell-quoted path',self.copy_shell_path); m.addAction('Properties',self.properties);
  if self._inside_nextcloud():m.addAction('Nextcloud public link…',self.nextcloud_share)
  m.exec(pane.view.viewport().mapToGlobal(pos))
 def _desktop_candidates(self,needle):
  roots=[Path.home()/'.local/share/applications',Path('/usr/local/share/applications'),Path('/usr/share/applications')]; out=[]
  for root in roots:
   if not root.exists():continue
   for f in root.glob('*.desktop'):
    try:
     text=f.read_text(errors='ignore'); low=(f.name+' '+text).casefold()
     if needle.casefold() in low and 'NoDisplay=true' not in text:out.append((f.name,f))
    except:pass
  return out
 def _preferred_niru_app(self,p):
  ext=p.suffix.lower(); needles=['nirupres'] if ext=='.nirupres' else ['nirunote'] if ext in ('.md','.markdown') else []
  for n in needles:
   hits=self._desktop_candidates(n)
   if hits:return hits[0][0]
  return None
 def _launch_desktop(self,desktop_id,p):
  gio=shutil.which('gio')
  if gio:
   r=subprocess.run([gio,'launch',desktop_id,str(p)],capture_output=True,text=True)
   if r.returncode==0:return True
  for root in [Path.home()/'.local/share/applications',Path('/usr/local/share/applications'),Path('/usr/share/applications')]:
   f=root/desktop_id
   if not f.exists():continue
   try:
    line=next(x.split('=',1)[1] for x in f.read_text(errors='ignore').splitlines() if x.startswith('Exec=')); args=shlex.split(line); args=[str(p) if x in ('%f','%F','%u','%U') else x for x in args if x not in ('%i','%c','%k')]; return run_detached(args)
   except:pass
  return False
 def open_path(self,p):
  p=Path(p)
  if p.is_dir():return self.active.go(p)
  app=self._preferred_niru_app(p)
  if app and self._launch_desktop(app,p):return True
  return QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
 def open_selected(self):
  s=self.selected()
  if len(s)==1:
   p=s[0]
   if p.is_file() and p.suffix.lower() in {'.mp3','.flac','.ogg','.opus','.m4a','.aac','.wav','.wma','.ape'}: return self.play_audio()
   self.open_path(p)
 def open_with(self):
  s=self.selected()
  if len(s)!=1 or s[0].is_dir():return self.err('Select exactly one file.')
  p=s[0]; apps=[]
  for needle in ('nirupres','nirunote','niruword'):
   for did,f in self._desktop_candidates(needle):
    if did not in [x[0] for x in apps]:apps.append((did,f.stem))
  if not apps:return self.err('No compatible NIRU desktop applications were detected. System Open remains available through the default association.')
  labels=[f'{name}  ·  {did}' for did,name in apps]; choice,ok=QInputDialog.getItem(self,'Open With',p.name,labels,0,False)
  if ok:self._launch_desktop(apps[labels.index(choice)][0],p)
 def _mime_for_extension(self,ext):
  return {'md':'text/markdown','markdown':'text/markdown','nirupres':'application/x-nirupres'}.get(ext.lstrip('.').lower())
 def _set_xdg_default(self,mime,desktop_id):
  exe=shutil.which('xdg-mime')
  if not exe:raise RuntimeError('xdg-mime is not installed.')
  r=subprocess.run([exe,'default',desktop_id,mime],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stderr.strip() or 'xdg-mime failed')
 def file_associations(self):
  d=NiruDialog(self); d.setWindowTitle('File Associations'); d.resize(720,420); l=QVBoxLayout(d); w=QTreeWidget(); w.setHeaderLabels(['Type','Preferred app','Detected desktop entry']); w.setRootIsDecorated(False)
  rows=[]
  for ext,label,needle in [('.nirupres','NIRUPRES','nirupres'),('.md / .markdown','NIRUNOTE','nirunote')]:
   hits=self._desktop_candidates(needle); did=hits[0][0] if hits else ''; it=QTreeWidgetItem(w,[ext,label,did or 'Not detected']); rows.append((it,ext,did))
  w.header().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); w.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents); w.header().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch); l.addWidget(QLabel('NIRUORG uses Linux/XDG defaults rather than a private association database.')); l.addWidget(w,1)
  row=QHBoxLayout(); setb=QPushButton('Set selected as system default'); refresh=QPushButton('Refresh detection'); row.addWidget(setb); row.addStretch(); row.addWidget(refresh); l.addLayout(row)
  def setdefault():
   idx=w.indexOfTopLevelItem(w.currentItem()) if w.currentItem() else -1
   if idx<0:return
   _,ext,did=rows[idx]
   if not did:return self.err('The application desktop entry was not detected.')
   try:
    mimes=['text/markdown'] if ext.startswith('.md') else ['application/x-nirupres']
    for mime in mimes:self._set_xdg_default(mime,did)
    self.info('File Associations',f'System default updated to {did}.')
   except Exception as e:self.err(e)
  setb.clicked.connect(setdefault); refresh.clicked.connect(lambda:(d.accept(),self.file_associations())); d.exec()
 def context_lens(self):
  base=self.current_dir(); facts=[]
  gitdir=(base/'.git')
  if gitdir.exists():
   facts.append('Git repository · metadata detected')
   head=gitdir/'HEAD'
   try:
    raw=head.read_text(errors='ignore').strip(); facts.append('Branch · '+(raw.rsplit('/',1)[-1] if raw.startswith('ref:') else 'detached HEAD'))
   except Exception:pass
  py=(base/'pyproject.toml').exists() or (base/'requirements.txt').exists(); node=(base/'package.json').exists()
  if py:facts.append('Python project'+(' · virtual environment detected' if any((base/x).exists() for x in ('.venv','venv')) else ''))
  if node:facts.append('Node project'+(' · node_modules present' if (base/'node_modules').is_dir() else ''))
  compose=next((base/x for x in ('compose.yaml','compose.yml','docker-compose.yml') if (base/x).exists()),None)
  if compose:facts.append(f'Docker Compose · {compose.name}')
  if (base/'README.md').exists():facts.append('Documentation · README.md')
  try:
   files=[x for x in base.iterdir() if x.is_file()]; dirs=sum(1 for x in base.iterdir() if x.is_dir()); size=sum(x.stat().st_size for x in files); imgs=sum(1 for x in files if (mimetypes.guess_type(x.name)[0] or '').startswith('image/')); media=sum(1 for x in files if (mimetypes.guess_type(x.name)[0] or '').startswith(('audio/','video/'))); facts.append(f'Folder · {len(files)} files · {dirs} folders · {human(size)} direct size')
   if files and imgs/len(files)>=.5:facts.append(f'Image collection · {imgs}/{len(files)} direct files')
   if files and media/len(files)>=.5:facts.append(f'Media collection · {media}/{len(files)} direct files')
  except Exception:pass
  self.info('Context Lens 2.0',str(base)+'\n\n'+('\n'.join(facts) if facts else 'No special project or media context detected.')+'\n\nFast local inspection only. No network calls, daemon or background indexing.')
 def _restore_session_state(self):
  if not self.restore_session:return
  p2=self.s.value('session_pane2',''); split=self.s.value('session_split',False,type=bool)
  try:
   left=json.loads(self.s.value('session_left_tabs','[]') or '[]'); right=json.loads(self.s.value('session_right_tabs','[]') or '[]')
   if left:self.pane1.restore_tabs(left)
   if split:
    self._show_right_pane(empty=True); self.pane2.restore_tabs(right) if right else self.pane2._insert_tab_state({'path':p2 or str(Path.home()),'history':[],'hist':-1,'pinned':False})
   active=self.s.value('session_active_pane','left'); self.set_active(self.pane2 if split and active=='right' else self.pane1)
  except Exception:
   if split and p2:self.pane2.show(); self.pane2.close_split.show(); self.pane2.go(p2,True)
 def _ssh_agent_environment(self,create=False):
  # Prefer an agent inherited from the desktop/session. ssh-add return code 0
  # (keys loaded) or 1 (agent reachable, no keys) both mean the socket works.
  inherited={k:os.environ.get(k,'') for k in ('SSH_AUTH_SOCK','SSH_AGENT_PID') if os.environ.get(k)}
  if inherited.get('SSH_AUTH_SOCK') and shutil.which('ssh-add'):
   try:
    r=subprocess.run(['ssh-add','-l'],env={**os.environ,**inherited},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2)
    if r.returncode in (0,1):return inherited
   except Exception:pass
  if self._private_ssh_agent_sock and Path(self._private_ssh_agent_sock).exists():
   return {'SSH_AUTH_SOCK':self._private_ssh_agent_sock,'SSH_AGENT_PID':str(self._private_ssh_agent_pid or '')}
  if not create:return {}
  agent=shutil.which('ssh-agent')
  if not agent:return {}
  state=Path.home()/'.local/state/niruorg'; state.mkdir(parents=True,exist_ok=True)
  requested_sock=state/f'ssh-agent-{os.getpid()}.sock'
  try:requested_sock.unlink(missing_ok=True)
  except Exception:pass
  # OpenSSH output differs slightly between distributions/builds. Parse the
  # environment it actually reports instead of assuming the requested socket
  # path exists synchronously. If -a is unsupported/broken, fall back to the
  # agent's native socket location.
  for cmd in ([agent,'-a',str(requested_sock),'-s'],[agent,'-s']):
   try:
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=5)
    if r.returncode!=0:continue
    ms=re.search(r'(?:^|[;\n]\s*)SSH_AUTH_SOCK=([^;\n]+)',r.stdout)
    mp=re.search(r'(?:^|[;\n]\s*)SSH_AGENT_PID=(\d+)',r.stdout)
    if not ms or not mp:continue
    sock=ms.group(1).strip().strip("'\""); pid=mp.group(1)
    env={'SSH_AUTH_SOCK':sock,'SSH_AGENT_PID':pid}
    # The environment printed by ssh-agent is authoritative. Some OpenSSH /
    # distribution combinations return a non-standard ssh-add -l status during
    # the tiny startup window even though the agent is healthy. Rejecting the
    # agent here made Unlock fail before ssh-add could ever ask for a passphrase.
    # Keep the parsed agent and let the interactive ssh-add / subsequent SSH
    # preflight perform the real authentication check.
    self._private_ssh_agent_pid=int(pid); self._private_ssh_agent_sock=sock
    return env
   except Exception:continue
  return {}
 def _stop_private_ssh_agent(self):
  pid=self._private_ssh_agent_pid; sock=self._private_ssh_agent_sock
  self._private_ssh_agent_pid=None; self._private_ssh_agent_sock=None
  if pid:
   try:os.kill(int(pid),15)
   except Exception:pass
  if sock:
   try:Path(sock).unlink(missing_ok=True)
   except Exception:pass
 def _load_mount_journal(self):
  """Load NIRUORG mount ownership metadata without touching any FUSE path."""
  try:
   raw=json.loads(self._mount_journal.read_text()) if self._mount_journal.exists() else {}
   if not isinstance(raw,dict):raw={}
  except Exception:raw={}
  self._orphan_mounts={str(k):v for k,v in raw.items() if isinstance(v,dict)}

 def _write_mount_journal(self):
  """Persist only mounts created by this process. Atomic replace avoids torn state."""
  try:
   self._mount_journal.parent.mkdir(parents=True,exist_ok=True)
   tmp=self._mount_journal.with_suffix('.tmp')
   payload={str(k):v for k,v in self._owned_mounts.items()}
   tmp.write_text(json.dumps(payload,indent=2,sort_keys=True))
   os.replace(tmp,self._mount_journal)
  except Exception:pass

 def _claim_mount(self,path,kind,name):
  """Record ownership only after a mount command succeeded and mountinfo confirms it."""
  mp=os.path.normpath(os.path.abspath(os.path.expanduser(str(path))))
  if not lexical_under(mp,Path.home()/'.local/share/niruorg/mounts'):return
  self._owned_mounts[mp]={'pid':os.getpid(),'kind':str(kind),'name':str(name),'created':time.time()}
  self._orphan_mounts.pop(mp,None); self._write_mount_journal()

 def _release_mount(self,path):
  mp=os.path.normpath(os.path.abspath(os.path.expanduser(str(path))))
  self._owned_mounts.pop(mp,None); self._orphan_mounts.pop(mp,None); self._write_mount_journal()

 def _detach_remote_models_for_shutdown(self):
  """Move QFileSystemModel away from FUSE before unmounting owned remotes."""
  home=str(Path.home())
  for pane in (self.pane1,self.pane2):
   if not pane.is_remote():continue
   try:
    pane.view.clearSelection(); pane.view.setRootIndex(QModelIndex()); pane.model.setRootPath(home)
   except Exception:pass
  QApplication.processEvents()

 def _unmount_owned_path(self,path,allow_lazy=True):
  """Bounded best-effort unmount. Never dereference the FUSE mount itself."""
  mp=os.path.normpath(os.path.abspath(os.path.expanduser(str(path))))
  if mp not in self._owned_mounts:return True
  if not path_is_mounted(mp):self._release_mount(mp); return True
  exe=shutil.which('fusermount3') or shutil.which('fusermount') or shutil.which('umount')
  if not exe:return False
  base=Path(exe).name
  attempts=[['-u',mp]] if 'fusermount' in base else [[mp]]
  if allow_lazy:
   attempts += ([['-uz',mp]] if 'fusermount' in base else [['-l',mp]])
  for args in attempts:
   try:
    r=subprocess.run([exe]+args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2)
    if r.returncode==0 or not path_is_mounted(mp):self._release_mount(mp); return True
   except subprocess.TimeoutExpired:pass
   except Exception:pass
  return not path_is_mounted(mp)

 def _cleanup_owned_mounts(self):
  # Snapshot because successful unmount mutates the ownership map.
  for mp in list(self._owned_mounts):self._unmount_owned_path(mp,True)

 def _shutdown_remote_resources(self):
  if self._shutdown_done:return
  self._shutdown_done=True; self._accept_worker_results=False
  self._remote_probe_tokens.clear(); self._remote_probe_pool.clear()
  # Remote workers have hard subprocess timeouts (<=4s). Drain them before
  # detaching/unmounting FUSE so no probe can race shutdown or outlive Main.
  self._remote_probe_pool.waitForDone(4500)
  self._detach_remote_models_for_shutdown()
  self._cleanup_owned_mounts()
  self._stop_private_ssh_agent()

 def closeEvent(self,event):
  if self.operations:
   box=QMessageBox(self); box.setWindowTitle('Transfers still running'); box.setText(f'{len(self.operations)} transfer operation(s) are still running.'); box.setInformativeText('NIRUORG will not unmount remote locations while a transfer is using them.'); keep=box.addButton('Keep NIRUORG open',QMessageBox.ButtonRole.AcceptRole); cancel=box.addButton('Cancel transfers and close',QMessageBox.ButtonRole.DestructiveRole); box.setDefaultButton(keep); box.exec()
   if box.clickedButton() is cancel:
    self._close_after_transfers=True
    for worker in list(self.operations):worker.cancel()
    self.status.setText('Cancelling transfers safely…'); event.ignore(); return
   event.ignore(); return
  if self.restore_session:
   self.s.setValue('session_pane1',str(Path.home()) if self.pane1.is_remote() else str(self.pane1.current)); self.s.setValue('session_pane2',str(Path.home()) if self.pane2.is_remote() else str(self.pane2.current)); self.s.setValue('session_split',self.pane2.isVisible()); self.s.setValue('session_left_tabs',json.dumps(self.pane1.export_tabs())); self.s.setValue('session_right_tabs',json.dumps(self.pane2.export_tabs())); self.s.setValue('session_active_pane','right' if self.active is self.pane2 else 'left')
  self._shutdown_remote_resources()
  super().closeEvent(event)
 def copy_path(self):
  items=self.selected(); text='\n'.join(str(p) for p in items) if items else str(self.current_dir()); QApplication.clipboard().setText(text); self.status.setText(f'Copied {len(items) if items else 1} path(s)')
 def copy_shell_path(self):
  items=self.selected(); text=' '.join(shlex.quote(str(p)) for p in items) if items else shlex.quote(str(self.current_dir())); QApplication.clipboard().setText(text); self.status.setText('Shell-quoted path copied')
 def new_folder(self):
  n,ok=QInputDialog.getText(self,'New folder','Name:')
  if ok and n.strip():
   try:(self.current_dir()/n.strip()).mkdir()
   except Exception as e:self.err(e)
 def rename(self):
  s=self.selected()
  if len(s)!=1:return
  src=s[0]; d=NiruDialog(self); d.setWindowTitle('Rename'); d.setMinimumWidth(460); l=QVBoxLayout(d); e=QLineEdit(src.name); l.addWidget(QLabel('New name')); l.addWidget(e); hint=QLabel('The extension is preserved in the selection. Existing names are rejected before rename.'); hint.setObjectName('muted'); hint.setWordWrap(True); l.addWidget(hint); b=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); [x.setIcon(QIcon()) for x in b.buttons()]; l.addWidget(b); b.accepted.connect(d.accept); b.rejected.connect(d.reject)
  stem_end=len(src.stem) if src.suffix else len(src.name); e.setSelection(0,stem_end); e.setFocus()
  if d.exec()!=QDialog.DialogCode.Accepted:return
  n=e.text().strip()
  if not n or n==src.name:return
  target=src.with_name(n)
  if target.exists():return self.err(f'Already exists: {target.name}')
  try:src.rename(target)
  except Exception as ex:self.err(ex)
 def copy(self):self.clip=self.selected(); self.cut_mode=False; self.update_status()
 def cut(self):self.clip=self.selected(); self.cut_mode=True; self.update_status()
 def paste(self):
  if not self.clip:return
  self.start_transfer(list(self.clip),self.current_dir(),self.cut_mode)
  if self.cut_mode:self.clip=[]; self.cut_mode=False
 def trash(self):
  for p in self.selected():
   try:
    if not QFile.moveToTrash(str(p)):raise RuntimeError(f'Could not move {p.name} to trash')
   except Exception as e:self.err(e);break
 def _confirm_permanent_delete(self,count):
  if not self.confirm_delete:return True
  return self.confirm('Delete permanently',f'Permanently delete {count} item(s)?\n\nThis cannot be undone.','Delete permanently')
 def permanent_delete(self):
  items=list(self.selected())
  if not items:return
  if not self._confirm_permanent_delete(len(items)):return
  deleted=0
  for p in items:
   try:
    if p.is_dir() and not p.is_symlink():shutil.rmtree(p)
    else:p.unlink()
    deleted+=1
   except Exception as e:self.err(e);break
  self.update_status()
  if deleted:self.status.setText(f'Permanently deleted {deleted} item(s)')
 def properties(self):
  s=self.selected()
  if len(s)!=1:return
  p=s[0]
  try:
   st=p.lstat(); typ='Directory' if p.is_dir() else (mimetypes.guess_type(p.name)[0] or 'File'); size='—' if p.is_dir() else human(st.st_size); target=f'\nTarget: {p.resolve()}' if p.is_symlink() else ''
   self.info('Properties',f'{p.name}\n\nType: {typ}\nSize: {size}\nPermissions: {stat.filemode(st.st_mode)} ({oct(st.st_mode & 0o777)})\nOwner UID:GID: {st.st_uid}:{st.st_gid}\nModified: {self.format_dt(st.st_mtime)}\nPath: {p}{target}')
  except Exception as e:self.err(e)
 def preview(self):
  s=self.selected()
  if len(s)!=1:return
  p=s[0]; d=NiruDialog(self); d.setWindowTitle(f'Inspect — {p.name}'); d.resize(800,650); l=QVBoxLayout(d); l.addWidget(QLabel(f'<b>{p.name}</b>'))
  mime=mimetypes.guess_type(p.name)[0] or ''
  if p.is_file() and mime.startswith('image/'):
   pix=QPixmap(str(p)); lab=QLabel(); lab.setAlignment(Qt.AlignmentFlag.AlignCenter); lab.setPixmap(pix.scaled(740,520,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); l.addWidget(lab,1); l.addWidget(QLabel(f'{pix.width()} × {pix.height()} · {human(p.stat().st_size)} · {mime}'))
  elif p.is_file() and p.stat().st_size<3_000_000 and (mime.startswith('text/') or mime in ('application/json','application/xml','application/javascript') or p.suffix.lower() in ('.md','.py','.js','.ts','.css','.toml','.yaml','.yml','.sh','.fish')):
   e=QPlainTextEdit(); e.setReadOnly(True); e.setPlainText(p.read_text(errors='replace')); l.addWidget(e,1)
  elif p.is_file() and (mime.startswith('audio/') or mime.startswith('video/')):
   info=self.media_info(p); lab=QLabel((info or 'Media file')+f'\n\nSize: {human(p.stat().st_size)}\nPath: {p}'); lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); l.addWidget(lab); play=QPushButton('Play with MPV'); play.clicked.connect(lambda:run_detached([shutil.which('mpv'),str(p)]) if shutil.which('mpv') else self.err('MPV is not installed.')); l.addWidget(play); l.addStretch()
  elif p.is_file() and (zipfile.is_zipfile(p) or tarfile.is_tarfile(p)):
   e=QPlainTextEdit(); e.setReadOnly(True)
   try:names=zipfile.ZipFile(p).namelist() if zipfile.is_zipfile(p) else tarfile.open(p).getnames(); e.setPlainText('\n'.join(names[:1000])+('\n…' if len(names)>1000 else ''))
   except Exception as x:e.setPlainText(str(x))
   l.addWidget(e,1)
  else:
   try:st=p.lstat(); info=f'Type: {"Directory" if p.is_dir() else mime or "File"}\nSize: {"—" if p.is_dir() else human(st.st_size)}\nPermissions: {stat.filemode(st.st_mode)}\nPath: {p}'
   except Exception as x:info=str(x)
   lab=QLabel(info); lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); l.addWidget(lab); l.addStretch()
  d.exec()
 def _remember_split_sizes(self,*_):
  if self.pane2.isVisible():
   sizes=self.split.sizes()
   if len(sizes)==2 and min(sizes)>0:self.settings.setValue('split_sizes',sizes)

 def _restore_split_sizes(self):
  raw=self.settings.value('split_sizes')
  try:vals=[int(x) for x in raw] if isinstance(raw,(list,tuple)) else []
  except Exception:vals=[]
  self.split.setSizes(vals if len(vals)==2 and min(vals)>0 else [1,1])

 def _remote_definition_for_path(self,path):
  for name,cfg in self._json_setting('servers_json').items():
   safe=''.join(c if c.isalnum() or c in '-_.' else '_' for c in name); mp=Path.home()/'.local/share/niruorg/mounts'/safe
   if lexical_under(path,mp):return (name,cfg.get('protocol','sftp'),mp,cfg.get('path','/'))
  for name in self._cloud_cache:
   mp=self._cloud_mountpoint(name)
   if lexical_under(path,mp):return (name,'CLOUD',mp,'/')
  return None
 def _identify_remote_path(self,pane,path):
  hit=self._remote_definition_for_path(path)
  if not hit:return False
  pane.bind_remote(*hit); return True
 def _start_worker(self,pool,worker,terminal=('done','failed')):
  """Start a QRunnable while retaining its Python/QObject signal wrappers.

  PySide does not make QRunnable ownership equivalent to Python wrapper
  ownership. A local-only reference can disappear while a queued signal still
  needs its QObject wrapper. Keep a strong reference until a terminal signal
  has been delivered and one more GUI turn has elapsed.
  """
  worker.setAutoDelete(False)
  self._worker_seq+=1; key=self._worker_seq; self._worker_refs[key]=worker
  released={'queued':False}
  def queue_release(*_):
   if released['queued']:return
   released['queued']=True
   QTimer.singleShot(0,lambda k=key:self._worker_refs.pop(k,None))
  connected=False
  for name in terminal:
   sig=getattr(getattr(worker,'signals',None),name,None)
   if sig is not None:
    sig.connect(queue_release); connected=True
  if not connected:
   raise RuntimeError(f'Worker {type(worker).__name__} has no terminal signal')
  pool.start(worker); return worker

 def _path_endpoint_meta(self,path):
  p=os.path.normpath(os.path.abspath(os.path.expanduser(str(path))))
  hit=self._remote_definition_for_path(Path(p))
  if not hit:return {'path':p,'remote':False,'mounted':True,'endpoint':'Local'}
  name,proto,mp,root=hit
  return {'path':p,'remote':True,'mounted':path_is_mounted(mp),'endpoint':name,'protocol':proto,'mount':str(mp)}
 def _remote_path(self,path):return bool(self._remote_definition_for_path(Path(os.path.abspath(os.path.expanduser(str(path))))))

 def navigate_remote_async(self,pane,path,push=True,leave_remote=False):
  if not pane.is_remote():return False
  self._remote_probe_seq+=1; token=self._remote_probe_seq; self._remote_probe_tokens[id(pane)]=token
  pane.current=Path(os.path.abspath(os.path.expanduser(str(path)))); pane.path.setText(str(pane.current)); pane.update_breadcrumbs(); pane.view.setEnabled(False); self.status.setText(f'{pane.remote_name} · Checking…')
  worker=RemoteProbeWorker(token,pane.current,pane.remote_mount)
  def done(result,p=pane,expected=token,ps=push,lr=leave_remote):
   if self._remote_probe_tokens.get(id(p))!=expected:return
   p.view.setEnabled(True)
   if result.get('ok'):
    p._commit_go(result['path'],ps,lr,True); self.status.setText(f'{p.remote_name} · Connected')
   else:
    p.update_breadcrumbs(); p._sync_tab(); self.status.setText(f'{p.remote_name} · {result.get("detail","Unavailable")}')
  worker.signals.done.connect(done); self._start_worker(self._remote_probe_pool,worker,('done',)); return True
 def _post_show_startup(self):
  self.startup_trace.mark('window shown / deferred start')
  if self._startup_requested_path:QTimer.singleShot(0,lambda:self.pane1.go(self._startup_requested_path))
  else:QTimer.singleShot(0,self._restore_session_state)
  QTimer.singleShot(25,self._discover_external_async)
 def _discover_external_async(self):
  # Module-level worker + explicit retention avoids PySide/Shiboken lifetime races.
  w=DiscoveryWorker()
  def done(r):
   if not self._accept_worker_results:return
   self._cloud_cache=list(r.get('cloud',[])); self._devices_cache=sorted(set(r.get('devices',[]))); self.build_sidebar(); self.startup_trace.mark('external discovery ready')
  w.signals.done.connect(done); self._start_worker(self._remote_probe_pool,w,('done',))
 def _show_right_pane(self,empty=False):
  if not self.pane2.isVisible():
   self.pane2.show(); self.pane2.close_split.show(); self._restore_split_sizes()
  if empty and self.pane2.tabs.count():
   self.pane2._tab_loading=True
   try:
    while self.pane2.tabs.count():self.pane2.tabs.removeTab(0)
    self.pane2._tab_states=[]
   finally:self.pane2._tab_loading=False
 def _right_tabs_exhausted(self):
  # Zero real tabs in the optional pane means split view is finished.
  self._hidden_right_tabs=None; self.pane2.hide(); self.pane2.close_split.hide(); self.set_active(self.pane1); self.pane1.view.setFocus(); self.update_status()
 def show_right_pane(self):
  self._show_right_pane(empty=False)
  if self.pane2.tabs.count()==0:
   if self._hidden_right_tabs:self.pane2.restore_tabs(self._hidden_right_tabs); self._hidden_right_tabs=None
   else:self.pane2._insert_tab_state({'path':str(self.pane1.current),'history':[],'hist':-1,'pinned':False})
  self.set_active(self.pane2)
 def toggle_split(self):
  if self.pane2.isVisible():self.close_split(self.pane2)
  else:self.show_right_pane()
  self.update_status()
 def close_split(self,pane=None):
  if not self.pane2.isVisible():return
  # Hiding a pane is not the same as closing its tabs. Keep its workspace for
  # this process so Ctrl+2 can bring it back exactly as it was.
  self.pane2._sync_tab(); self._hidden_right_tabs=self.pane2.export_tabs() if self.pane2.tabs.count() else None
  self.pane2.hide(); self.pane2.close_split.hide(); self.set_active(self.pane1); self.pane1.view.setFocus(); self.update_status()
 def set_view(self,mode):
  if mode=='gallery':return self.gallery()
  for p in (self.pane1,self.pane2):
   p.view.setIconSize(QSize(20,20)); p.view.header().show()
 def image_viewer(self,files,start=0,fullscreen=False,parent=None):
  files=[Path(x) for x in files]
  if not files:return
  d=ImageViewerDialog(parent or self); d.setWindowTitle('Gallery Focus'); d.setStyleSheet(self.styleSheet()); d.setModal(True); d.setMinimumSize(640,420)
  lay=QVBoxLayout(d); lay.setContentsMargins(10,10,10,8); lay.setSpacing(8)
  toolbar=QHBoxLayout(); toolbar.setSpacing(6); prev=QPushButton('Previous'); nxt=QPushButton('Next'); fit=QPushButton('100%'); full=QPushButton('Exit fullscreen' if fullscreen else 'Fullscreen'); close=QPushButton('Close'); hint=QLabel('←/→ navigate   Space next   F fit/100%   F11 fullscreen   Esc back'); hint.setObjectName('muted')
  toolbar.addWidget(prev); toolbar.addWidget(nxt); toolbar.addWidget(fit); toolbar.addStretch(); toolbar.addWidget(hint); toolbar.addStretch(); toolbar.addWidget(full); toolbar.addWidget(close); lay.addLayout(toolbar)
  lab=QLabel(); lab.setAlignment(Qt.AlignmentFlag.AlignCenter); lab.setMinimumSize(1,1); lab.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding); info=QLabel(); info.setAlignment(Qt.AlignmentFlag.AlignCenter); info.setObjectName('muted'); lay.addWidget(lab,1); lay.addWidget(info)
  state={'i':max(0,min(start,len(files)-1)),'fit':True,'fullscreen':bool(fullscreen),'pix':QPixmap()}
  def render():
   pix=state['pix']
   if pix.isNull():lab.clear(); return
   if state['fit']:
    target=lab.contentsRect().size(); shown=pix.scaled(max(1,target.width()),max(1,target.height()),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
   else:shown=pix
   lab.setPixmap(shown)
  def show_image():
   p=files[state['i']]; pix=QPixmap(str(p)); state['pix']=pix; info.setText(f'{p.name}   ·   {pix.width()} × {pix.height()}   ·   {state["i"]+1}/{len(files)}'); fit.setText('100%' if state['fit'] else 'Fit'); render()
  def step(n):state.update(i=(state['i']+n)%len(files)); show_image()
  def toggle_fit():state.update(fit=not state['fit']); render(); fit.setText('100%' if state['fit'] else 'Fit')
  def toggle_full():
   state['fullscreen']=not state['fullscreen']
   if state['fullscreen']:d.showFullScreen(); full.setText('Exit fullscreen')
   else:d.showNormal(); d.resize(1100,780); full.setText('Fullscreen')
   QTimer.singleShot(30,render)
  def escape():
   if state['fullscreen']:toggle_full()
   else:d.reject()
  d.escape_handler=escape; d.resize_handler=lambda: render() if state['fit'] else None
  prev.clicked.connect(lambda:step(-1)); nxt.clicked.connect(lambda:step(1)); fit.clicked.connect(toggle_fit); full.clicked.connect(toggle_full); close.clicked.connect(d.reject)
  QShortcut(QKeySequence('Right'),d,activated=lambda:step(1)); QShortcut(QKeySequence('Space'),d,activated=lambda:step(1)); QShortcut(QKeySequence('Left'),d,activated=lambda:step(-1)); QShortcut(QKeySequence('Backspace'),d,activated=lambda:step(-1)); QShortcut(QKeySequence('Home'),d,activated=lambda:(state.update(i=0),show_image())); QShortcut(QKeySequence('End'),d,activated=lambda:(state.update(i=len(files)-1),show_image())); QShortcut(QKeySequence('F'),d,activated=toggle_fit); QShortcut(QKeySequence('F11'),d,activated=toggle_full)
  if fullscreen:d.showFullScreen()
  else:d.resize(1100,780)
  QTimer.singleShot(30,show_image); d.exec()
 def gallery(self):
  try:files=sorted([p for p in self.current_dir().iterdir() if p.is_file() and (mimetypes.guess_type(p.name)[0] or '').startswith('image/')],key=lambda p:p.name.lower())
  except Exception as e:return self.err(e)
  if not files:return self.err('No images in this folder.')
  d=NiruDialog(self); d.setWindowTitle(f'Gallery — {self.current_dir().name}'); d.resize(1040,720); lay=QVBoxLayout(d); top=QHBoxLayout(); summary=QLabel(f'<b>{self.current_dir().name}</b>   ·   {len(files)} images'); summary.setObjectName('muted'); focus=QPushButton('Focus / Fullscreen'); slide=QPushButton('Slideshow'); close=QPushButton('Close'); top.addWidget(summary); top.addStretch(); top.addWidget(QLabel('Enter/F11 focus · Esc close')); top.addWidget(focus); top.addWidget(slide); top.addWidget(close); lay.addLayout(top); w=QListWidget(); w.setViewMode(QListView.ViewMode.IconMode); w.setResizeMode(QListView.ResizeMode.Adjust); w.setMovement(QListView.Movement.Static); w.setIconSize(QSize(144,108)); w.setGridSize(QSize(176,146)); w.setWordWrap(True); w.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
  placeholder=self.active.icons._icon('image')
  for p in files:
   it=QListWidgetItem(placeholder,p.name); it.setData(Qt.ItemDataRole.UserRole,str(p)); w.addItem(it)
  state={'i':0}
  def batch():
   stop=min(state['i']+8,len(files))
   for i in range(state['i'],stop):
    pix=QPixmap(str(files[i]))
    if not pix.isNull():w.item(i).setIcon(QIcon(pix.scaled(144,108,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)))
   state['i']=stop
   if stop<len(files):QTimer.singleShot(1,batch)
  def idx():return max(0,w.currentRow())
  def open_focus(*_):self.image_viewer(files,idx(),True,d)
  w.itemDoubleClicked.connect(open_focus); focus.clicked.connect(open_focus); slide.clicked.connect(lambda:self.image_viewer(files,idx(),True,d)); close.clicked.connect(d.accept); QShortcut(QKeySequence('Return'),d,activated=open_focus); QShortcut(QKeySequence('F11'),d,activated=open_focus); lay.addWidget(w,1); QTimer.singleShot(0,batch); d.exec()
 def slideshow(self):
  files=sorted([p for p in self.current_dir().iterdir() if p.is_file() and (mimetypes.guess_type(p.name)[0] or '').startswith('image/')],key=lambda p:p.name.lower())
  if not files:return self.err('No images in this folder.')
  self.image_viewer(files,0,True)
 def terminal_here(self):
  s=self.selected(); p=s[0] if len(s)==1 and s[0].is_dir() else self.current_dir(); pane=self.active
  if not self.terminal or not (Path(self.terminal).exists() or shutil.which(Path(self.terminal).name)):return self.err('No terminal configured. Set one in Settings.')
  if pane.is_remote():
   cfg=self._json_setting('servers_json').get(pane.remote_name,{}); host=cfg.get('host',pane.remote_name); user=cfg.get('user',''); port=str(cfg.get('port',22)); dest=(user+'@' if user else '')+host; remote=pane.display_path(); cmd=['ssh','-t','-p',port,dest,f'cd {shlex.quote(remote)} && exec fish -l']
   return run_detached([self.terminal,'-e']+cmd) if 'kitty' in self.terminal else run_detached([self.terminal,'-e']+cmd)
  run_detached([self.terminal,'--directory',str(p)] if 'kitty' in self.terminal else [self.terminal],str(p))
 def _audio_files(self):
  exts={'.mp3','.flac','.ogg','.opus','.m4a','.aac','.wav','.wma','.ape'}; selected=[p for p in self.selected() if p.is_file() and p.suffix.lower() in exts]
  if selected:return selected
  try:return sorted([p for p in self.current_dir().iterdir() if p.is_file() and p.suffix.lower() in exts],key=lambda p:p.name.lower())
  except:return []
 def niru_player(self,files=None,start=0):
  files=files or self._audio_files()
  if not files:return self.err('Select an audio file, or open a folder containing music.')
  exe=shutil.which('mpv')
  if not exe:return self.err('NIRU Player uses MPV as its playback backend. Install mpv, or choose another player in Settings → Audio playback.')
  d=NiruDialog(self); d.setWindowTitle('NIRU Player'); d.resize(680,300); d.setMinimumWidth(560); l=QVBoxLayout(d); l.setContentsMargins(24,20,24,18); l.setSpacing(10)
  head=QHBoxLayout(); now=QLabel('NOW PLAYING'); now.setObjectName('muted'); queue=QLabel(); queue.setObjectName('muted'); queue.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter); head.addWidget(now); head.addStretch(); head.addWidget(queue); l.addLayout(head)
  title=QLabel(); title.setWordWrap(True); title.setStyleSheet('font-size: 18px; font-weight: 600;'); meta=QLabel(); meta.setObjectName('muted'); meta.setWordWrap(True); l.addWidget(title); l.addWidget(meta); l.addSpacing(8)
  slider=QSlider(Qt.Orientation.Horizontal); slider.setRange(0,1000); slider.setMinimumHeight(22); l.addWidget(slider)
  timeline=QHBoxLayout(); elapsed=QLabel('00:00'); elapsed.setObjectName('muted'); duration=QLabel('00:00'); duration.setObjectName('muted'); timeline.addWidget(elapsed); timeline.addStretch(); timeline.addWidget(duration); l.addLayout(timeline)
  row=QHBoxLayout(); row.setSpacing(6); prev=QPushButton('Previous'); play=QPushButton('Pause'); nxt=QPushButton('Next'); stop=QPushButton('Stop'); close=QPushButton('Close'); row.addWidget(prev); row.addWidget(play); row.addWidget(nxt); row.addWidget(stop); row.addStretch(); row.addWidget(QLabel('Space play/pause   ←/→ ±10 s')); row.addStretch(); row.addWidget(close); l.addLayout(row)
  state={'i':max(0,min(start,len(files)-1)),'drag':False,'manual':False,'paused':False}; runtime=Path(os.getenv('XDG_RUNTIME_DIR','/tmp'))/f'niruorg-mpv-{os.getpid()}-{int(time.time()*1000)}.sock'; proc=QProcess(d); proc.setProgram(exe); proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
  def fmt(v):
   try:v=max(0,int(float(v))); return f'{v//60:02d}:{v%60:02d}'
   except:return '00:00'
  def command(cmd):
   try:
    c=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); c.settimeout(.15); c.connect(str(runtime)); c.sendall((json.dumps({'command':cmd})+'\n').encode()); c.close(); return True
   except:return False
  def launch(i):
   state['i']=i%len(files); state['manual']=False; state['paused']=False; p=files[state['i']]; title.setText(p.stem); meta.setText(f'{p.parent.name}   ·   {p.suffix[1:].upper()}'); queue.setText(f'{state["i"]+1} / {len(files)}'); play.setText('Pause'); elapsed.setText('00:00'); duration.setText('00:00'); slider.setValue(0); proc.setArguments(['--no-video','--really-quiet','--input-ipc-server='+str(runtime),'--',str(p)]); proc.start()
  def next_track(n=1):
   state['manual']=True
   if proc.state()!=QProcess.ProcessState.NotRunning:proc.kill(); proc.waitForFinished(300)
   try:runtime.unlink(missing_ok=True)
   except:pass
   launch((state['i']+n)%len(files))
  def poll():
   if proc.state()==QProcess.ProcessState.NotRunning:return
   try:
    c=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); c.settimeout(.08); c.connect(str(runtime)); c.sendall((json.dumps({'command':['get_property','time-pos']})+'\n'+json.dumps({'command':['get_property','duration']})+'\n').encode()); raw=b''
    while raw.count(b'\n')<2:raw+=c.recv(4096)
    c.close(); vals=[json.loads(x).get('data') for x in raw.splitlines()[:2]]; pos,dur=vals
    if dur and not state['drag']:slider.setValue(int(max(0,min(1,float(pos or 0)/float(dur)))*1000))
    elapsed.setText(fmt(pos)); duration.setText(fmt(dur))
   except:pass
  def toggle():
   if command(['cycle','pause']):state['paused']=not state['paused']; play.setText('Play' if state['paused'] else 'Pause')
  def seek(v):
   try:
    c=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); c.settimeout(.1); c.connect(str(runtime)); c.sendall((json.dumps({'command':['get_property','duration']})+'\n').encode()); dur=json.loads(c.recv(4096).splitlines()[0]).get('data'); c.close()
    if dur:command(['set_property','time-pos',float(dur)*v/1000])
   except:pass
  def stop_playback():
   state['manual']=True; proc.kill(); slider.setValue(0); elapsed.setText('00:00'); play.setText('Play'); state['paused']=True
  def finished(*_):
   if state['manual']:state['manual']=False; return
   if d.isVisible():QTimer.singleShot(120,lambda:launch((state['i']+1)%len(files)))
  play.clicked.connect(toggle); prev.clicked.connect(lambda:next_track(-1)); nxt.clicked.connect(lambda:next_track(1)); stop.clicked.connect(stop_playback); close.clicked.connect(d.accept); slider.sliderPressed.connect(lambda:state.update(drag=True)); slider.sliderReleased.connect(lambda:(seek(slider.value()),state.update(drag=False))); proc.finished.connect(finished); timer=QTimer(d); timer.timeout.connect(poll); timer.start(400); QShortcut(QKeySequence('Space'),d,activated=toggle); QShortcut(QKeySequence('Right'),d,activated=lambda:command(['seek',10,'relative'])); QShortcut(QKeySequence('Left'),d,activated=lambda:command(['seek',-10,'relative'])); launch(state['i']); d.exec(); timer.stop(); state['manual']=True; proc.kill(); proc.waitForFinished(300)
  try:runtime.unlink(missing_ok=True)
  except:pass
 def mpv(self):
  s=self.selected(); exe=shutil.which('mpv')
  if not exe:return self.err('MPV is not installed.')
  items=s or [self.current_dir()]; run_detached([exe]+[str(x) for x in items])
 def play_audio(self):
  files=self._audio_files()
  if not files:return self.err('Select an audio file, or open a folder containing music.')
  pref=getattr(self,'audio_player','NIRU Player (MPV backend)')
  if pref.startswith('NIRU Player'):return self.niru_player(files,0)
  if pref=='System default':return QDesktopServices.openUrl(QUrl.fromLocalFile(str(files[0])))
  cmd={'MPV':'mpv','VLC':'vlc','cmus':'cmus'}.get(pref)
  exe=shutil.which(cmd) if cmd else None
  if not exe:return self.err(f'{pref} is not installed.')
  if pref=='cmus':
   if self.terminal and 'kitty' in self.terminal:return run_detached([self.terminal,'-e',exe,str(files[0])])
   return run_detached([exe,str(files[0])])
  run_detached([exe]+[str(x) for x in files])
 def localsend(self):
  s=self.selected(); exe=shutil.which('localsend') or shutil.which('localsend_app')
  if not exe:return self.err('LocalSend is not installed or no CLI launcher was found.')
  if s:run_detached([exe]+[str(x) for x in s])
 def temporary_split(self):
  path=QFileDialog.getExistingDirectory(self,'Temporary split',str(self.current_dir()))
  if not path:return
  if not self.pane2.isVisible():self.pane2.setVisible(True)
  self.pane2.go(path,True); self.set_active(self.pane2); self.status.setText('Temporary split · Esc or Ctrl+2 when finished')
 def archive_browser(self):
  sel=self.selected()
  if len(sel)!=1:return self.err('Select one archive.')
  p=sel[0]
  try:
   if zipfile.is_zipfile(p): names=zipfile.ZipFile(p).namelist(); kind='zip'
   elif tarfile.is_tarfile(p): names=tarfile.open(p).getnames(); kind='tar'
   else:return self.err('This archive format cannot be browsed internally yet.')
  except Exception as e:return self.err(e)
  d=NiruDialog(self); d.setWindowTitle(f'Archive — {p.name}'); d.resize(820,600); l=QVBoxLayout(d); q=QLineEdit(); q.setPlaceholderText('Filter archive…'); w=QListWidget(); w.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
  def fill(t=''):
   w.clear(); needle=t.casefold()
   for n in names:
    if not needle or needle in n.casefold():w.addItem(n)
  fill(); q.textChanged.connect(fill); l.addWidget(q); l.addWidget(w,1); row=QHBoxLayout(); extract=QPushButton('Extract selected…'); close=QPushButton('Close'); row.addWidget(extract); row.addStretch(); row.addWidget(close); l.addLayout(row); close.clicked.connect(d.reject)
  def do_extract():
   chosen=[x.text() for x in w.selectedItems()]
   if not chosen:return
   out=QFileDialog.getExistingDirectory(d,'Extract selected to',str(self.current_dir()))
   if not out:return
   try:
    base=Path(out).resolve()
    if kind=='zip':
     safe_extract_zip(p,base,chosen)
    else:
     safe_extract_tar(p,base,chosen)
    self.status.setText(f'Extracted {len(chosen)} archive item(s)'); d.accept()
   except Exception as e:self.err(e)
  extract.clicked.connect(do_extract); d.exec()
 def path_actions(self,path=None):
  p=Path(path or self.current_dir()); m=QMenu(self); op=m.addAction('Open'); other=m.addAction(self.open_other_label()); basket=m.addAction('Add to Work Basket'); m.addSeparator(); term=m.addAction('Terminal here'); cp=m.addAction('Copy path'); sh=m.addAction('Add as Shortcut'); storage=m.addAction('Storage info'); act=m.exec(QCursor.pos())
  if act==op:self.active.go(p)
  elif act==other:
   if not self.pane2.isVisible():self.pane2.show(); self.pane2.close_split.show()
   target=self.pane2 if self.active is self.pane1 else self.pane1; target.go(p); self.set_active(target)
  elif act==basket:self.add_dropzone([p])
  elif act==term:run_detached([self.terminal,'--working-directory',str(p)]) if self.terminal and 'kitty' in Path(self.terminal).name else self.terminal_here()
  elif act==cp:QApplication.clipboard().setText(str(p))
  elif act==sh:self.add_shortcuts([str(p)])
  elif act==storage:self.storage_view()
 def extract(self):
  s=self.selected()
  if len(s)!=1 or not s[0].is_file():return
  p=s[0]; out=p.parent
  try:
   if zipfile.is_zipfile(p):safe_extract_zip(p,out)
   elif tarfile.is_tarfile(p):safe_extract_tar(p,out)
   elif shutil.which('7z'):subprocess.Popen(['7z','x',str(p),f'-o{out}'])
   else:raise RuntimeError('Unsupported archive or 7z is not installed.')
  except Exception as e:self.err(e)
 def compress(self):
  s=self.selected()
  if not s:return
  dest,_=QFileDialog.getSaveFileName(self,'Create ZIP',str(self.current_dir()/'archive.zip'),'ZIP (*.zip)')
  if not dest:return
  try:
   with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
    for p in s:
     if p.is_dir():
      for f in p.rglob('*'):
       if f.is_file():z.write(f,f.relative_to(p.parent))
     else:z.write(p,p.name)
  except Exception as e:self.err(e)
 def checksum(self):
  import hashlib
  s=self.selected()
  if len(s)!=1 or not s[0].is_file():return
  try:
   h=hashlib.sha256()
   with s[0].open('rb') as f:
    for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
   QApplication.clipboard().setText(h.hexdigest()); self.info('SHA-256',h.hexdigest()+'\n\nCopied to clipboard.')
  except Exception as e:self.err(e)
 def bulk_rename(self):
  s=self.selected()
  if len(s)<2:return self.err('Select at least two items.')
  pattern,ok=QInputDialog.getText(self,'Bulk rename','Pattern ({name}, {n}, {ext}):',text='{name}-{n}{ext}')
  if not ok:return
  preview=[]
  for i,p in enumerate(s,1):preview.append((p,p.with_name(pattern.replace('{name}',p.stem).replace('{n}',f'{i:02d}').replace('{ext}',p.suffix))))
  if not self.confirm('Bulk rename','Rename:\n\n'+'\n'.join(f'{a.name} → {b.name}' for a,b in preview[:20])+('\n…' if len(preview)>20 else ''),'Rename'):return
  try:
   for a,b in preview:a.rename(b)
  except Exception as e:self.err(e)
 def _save_work_basket(self):
  self.dropzone=list(dict.fromkeys(self.dropzone)); self.s.setValue('work_basket',self.dropzone); self.build_sidebar()
 def add_dropzone(self,items=None):
  items=list(items if items is not None else self.selected()); added=0
  for p in items:
   sp=str(p)
   if sp not in self.dropzone:self.dropzone.append(sp); added+=1
  if added:self._save_work_basket()
  self.status.setText(f'Work Basket · {len(self.dropzone)} item(s)')
 def show_dropzone(self):
  d=NiruDialog(self); d.setWindowTitle(f'Work Basket — {len(self.dropzone)} item(s)'); d.resize(860,540); l=QVBoxLayout(d)
  intro=QLabel('Temporary working set across local and remote locations. Items are references; removing them here never deletes the original.'); intro.setObjectName('muted'); intro.setWordWrap(True); l.addWidget(intro)
  w=WorkBasketList(); w.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); l.addWidget(w,1)
  states={}; metas={}; generation=object(); d._basket_generation=generation
  def populate(rows):
   if not d.isVisible() or getattr(d,'_basket_generation',None) is not generation:return
   w.clear(); states.clear(); metas.clear()
   for row in rows:
    x=row['path']; meta=row.get('meta',{}); state=meta.get('state','unavailable'); states[x]=state; metas[x]=meta; p=Path(x); endpoint=row.get('endpoint','Local')
    mark={'available':'●','offline':'○','missing':'×','unavailable':'!'}.get(state,'?'); label={'available':'Available','offline':'Offline','missing':'Missing','unavailable':'Unavailable'}.get(state,state.title())
    it=QListWidgetItem(f'{mark}  {p.name or x}    ·    {endpoint}    ·    {label}'); it.setToolTip(x); it.setData(Qt.ItemDataRole.UserRole,x); w.addItem(it)
  for x in self.dropzone:
   p=Path(x); it=QListWidgetItem(f'…  {p.name or x}    ·    Checking…'); it.setToolTip(x); it.setData(Qt.ItemDataRole.UserRole,x); w.addItem(it)
  def scan():
   payload=[self._path_endpoint_meta(x) for x in self.dropzone]; worker=MetadataWorker('basket',payload)
   worker.signals.done.connect(lambda r:populate(r.get('rows',[])) if self._accept_worker_results else None); worker.signals.failed.connect(lambda e:self.status.setText('Work Basket metadata unavailable · '+str(e))); self._start_worker(self._remote_probe_pool,worker)
  QTimer.singleShot(0,scan)
  row=QHBoxLayout(); clear=QPushButton('Clear'); remove=QPushButton('Remove selected'); missingb=QPushButton('Remove missing'); collection=QPushButton('Save as Collection'); archive=QPushButton('Compress…'); local=QPushButton('LocalSend'); action=QPushButton('Action…'); recipe=QPushButton('Recipe…'); move=QPushButton('Move to active folder'); send=QPushButton('Copy to active folder')
  for b in (clear,remove,missingb,collection):row.addWidget(b)
  row.addStretch()
  for b in (archive,local,action,recipe,move,send):row.addWidget(b)
  l.addLayout(row)
  def clearall():self.dropzone.clear(); self._save_work_basket(); d.accept()
  clear.clicked.connect(clearall)
  def rem():
   for it in list(w.selectedItems()):
    x=it.data(Qt.ItemDataRole.UserRole)
    if x in self.dropzone:self.dropzone.remove(x)
    w.takeItem(w.row(it))
   self._save_work_basket()
  remove.clicked.connect(rem)
  def remove_missing():
   self.dropzone=[x for x in self.dropzone if states.get(x)!='missing']; self._save_work_basket(); d.accept(); QTimer.singleShot(0,self.show_dropzone)
  missingb.clicked.connect(remove_missing)
  def reveal(it):
   x=it.data(Qt.ItemDataRole.UserRole); state=states.get(x)
   if state!='available':return self.status.setText(f'Work Basket · {state or "Checking"}')
   p=Path(x); self.active.go(p if metas.get(x,{}).get('dir') else p.parent); d.accept()
  w.itemDoubleClicked.connect(reveal)
  def dropped(paths):self.add_dropzone([Path(x) for x in paths]); d.accept(); QTimer.singleShot(0,self.show_dropzone)
  w.pathsDropped.connect(dropped)
  def staged():return [Path(x) for x in self.dropzone if states.get(x)=='available']
  def snd():
   items=staged()
   if items:self.start_transfer(items,self.current_dir(),False); d.accept()
  def savecol():
   items=staged()
   if not items:return
   name,ok=QInputDialog.getText(d,'Collection','Name:')
   if ok and name.strip():
    data=self._json_setting('collections_json'); data[name.strip()]=[str(x) for x in items]; self._save_json('collections_json',data); self.build_sidebar(); self.status.setText(f'Collection saved · {name.strip()}')
  def zipstage():
   items=staged()
   if not items:return self.status.setText('Work Basket · no available items selected')
   if any(self._remote_path(x) for x in items):return self.err('Compressing remote Work Basket items directly is disabled because it can block on a network filesystem. Copy them to a local folder first.')
   dest,_=QFileDialog.getSaveFileName(d,'Create ZIP',str(self.current_dir()/'staged.zip'),'ZIP (*.zip)')
   if not dest:return
   self.status.setText('Compressing Work Basket…')
   try:
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
     for item in items:
      if item.is_dir():
       for f in item.rglob('*'):
        if f.is_file():z.write(f,arcname=str(Path(item.name)/f.relative_to(item)))
      elif item.is_file():z.write(item,arcname=item.name)
    self.status.setText(f'Created · {dest}')
   except Exception as e:self.err(e)
  def sendlocal():
   exe=shutil.which('localsend'); items=staged()
   if not exe:return self.err('LocalSend is not installed.')
   if items:run_detached([exe]+[str(x) for x in items]); self.status.setText(f'LocalSend · {len(items)} staged item(s)')
  collection.clicked.connect(savecol); archive.clicked.connect(zipstage); local.clicked.connect(sendlocal); send.clicked.connect(snd)
  move.clicked.connect(lambda:(self.start_transfer(staged(),self.current_dir(),True),d.accept()) if staged() else None); action.clicked.connect(lambda:self.run_niru_action(staged())); recipe.clicked.connect(lambda:self.run_recipe(staged())); d.exec()
 def _transfer_to_other_pane(self,move=False,items=None):
  if not self.pane2.isVisible():return self.err('Enable Split View first (Ctrl+2).')
  src=self.active; dst=self.pane2 if src is self.pane1 else self.pane1; items=list(items or src.selected())
  if not items:return
  verb='Move' if move else 'Copy'; target=self.pane_target_label(dst)
  if src.is_remote() or dst.is_remote() or move:
   if not self.confirm(f'{verb} to {self.other_side(src)} pane',f'{verb} {len(items)} item(s) →\n{target}?',verb):return
  self.start_transfer(items,dst.current,move,self.pane_target_label(src),target)
 def send_other_pane(self):self._transfer_to_other_pane(False)
 def move_other_pane(self):self._transfer_to_other_pane(True)
 def handle_pane_drop(self,dst,items,drop_action,src=None,target_dir=None):
  # Cross-pane DnD is an explicit copy operation. Do not route it through
  # whichever pane happened to be active: Wayland focus can change during drag.
  src=src or (self.pane2 if dst is self.pane1 else self.pane1)
  target=Path(target_dir or dst.current); items=[Path(x) for x in items]
  if not items:return
  source_label=self.pane_target_label(src) if src in (self.pane1,self.pane2) else 'External'
  dest_label=self.pane_target_label(dst)
  # Drag-and-drop copy is already an explicit user action and is non-destructive
  # to the source. Do not add a second confirmation step. This also avoids a
  # modal-dialog round trip in the DnD path. Existing-name conflicts are still
  # handled explicitly by the transfer conflict policy.
  self.set_active(dst); self.start_transfer(items,target,False,source_label,dest_label)
 def compare_panes(self):
  if not self.pane2.isVisible():return self.err('Enable Split View first (Ctrl+2).')
  left,right=self.pane1.current,self.pane2.current
  d=NiruDialog(self); d.setWindowTitle('Compare Workspace'); d.resize(1000,650); l=QVBoxLayout(d); l.addWidget(QLabel(f'<b>{self.pane_target_label(self.pane1)}</b>  ↔  <b>{self.pane_target_label(self.pane2)}</b>'))
  summary=QLabel('Comparing safely…'); summary.setObjectName('muted'); l.addWidget(summary); w=QTreeWidget(); w.setHeaderLabels(['Name','Status','Left','Right']); w.setRootIsDecorated(False); w.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); l.addWidget(w,1)
  hint=QLabel('Metadata comparison is asynchronous and remote-safe. Nothing is synchronized automatically; transfers are always explicit.'); hint.setObjectName('muted'); hint.setWordWrap(True); l.addWidget(hint)
  row=QHBoxLayout(); recv=QPushButton('← Copy selected'); send=QPushButton('Copy selected →'); refresh=QPushButton('Refresh'); close=QPushButton('Close'); recv.setEnabled(False); send.setEnabled(False); row.addWidget(recv); row.addWidget(send); row.addWidget(refresh); row.addStretch(); row.addWidget(close); l.addLayout(row)
  cache={'left':{},'right':{}}
  def render(r):
   if not d.isVisible():return
   lm,rm=r.get('left'),r.get('right'); le,re=r.get('left_error'),r.get('right_error')
   if lm is None or rm is None:
    summary.setText(f'Left: {le or "OK"} · Right: {re or "OK"}'); return
   cache['left'],cache['right']=lm,rm; w.clear(); counts={}
   for name in sorted(set(lm)|set(rm),key=str.casefold):
    a,b=lm.get(name),rm.get(name); la=ra='—'
    if a is None:status='Right only'; ra='Folder' if b['dir'] else human(b['size'])
    elif b is None:status='Left only'; la='Folder' if a['dir'] else human(a['size'])
    elif a['dir']!=b['dir']:status='Changed'
    elif a['dir']:status='Folder'; la=ra='Folder'
    else:
     la,ra=human(a['size']),human(b['size']); status='Same' if a['size']==b['size'] and int(a['mtime'])==int(b['mtime']) else ('Newer left' if a['mtime']>b['mtime'] else 'Newer right' if b['mtime']>a['mtime'] else 'Changed')
    counts[status]=counts.get(status,0)+1; it=QTreeWidgetItem(w,[name,status,la,ra]); it.setData(0,Qt.ItemDataRole.UserRole,name)
   w.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
   for i in range(1,4):w.header().setSectionResizeMode(i,QHeaderView.ResizeMode.ResizeToContents)
   summary.setText(' · '.join(f'{k}: {v}' for k,v in counts.items() if v)); recv.setEnabled(True); send.setEnabled(True)
  def scan():
   summary.setText('Comparing safely…'); recv.setEnabled(False); send.setEnabled(False)
   worker=MetadataWorker('compare',{'left':self._path_endpoint_meta(left),'right':self._path_endpoint_meta(right)}); worker.signals.done.connect(render); worker.signals.failed.connect(lambda e:summary.setText('Compare failed · '+str(e))); self._start_worker(self._remote_probe_pool,worker)
  def selected_names():return [it.data(0,Qt.ItemDataRole.UserRole) for it in w.selectedItems()]
  def transfer(src,dst,side):
   items=[src/n for n in selected_names() if n in cache[side]]
   if not items:return self.err('Select one or more items that exist on the source side.')
   self.start_transfer(items,dst,False)
  send.clicked.connect(lambda:transfer(left,right,'left')); recv.clicked.connect(lambda:transfer(right,left,'right')); refresh.clicked.connect(scan); close.clicked.connect(d.accept); QTimer.singleShot(0,scan); d.exec()
 def choose_conflict_policy(self,conflicts,dst=None):
  if not conflicts:return 'ask'
  box=QMessageBox(self); box.setWindowTitle('Name conflict'); box.setText(f'{len(conflicts)} item(s) already exist in the destination.'); box.setInformativeText('Choose how NIRUORG should handle conflicts for this operation.'); rep=box.addButton('Replace',QMessageBox.ButtonRole.DestructiveRole); keep=box.addButton('Keep both',QMessageBox.ButtonRole.AcceptRole); skip=box.addButton('Skip existing',QMessageBox.ButtonRole.ActionRole); box.addButton(QMessageBox.StandardButton.Cancel); box.setDefaultButton(keep); box.exec(); b=box.clickedButton()
  return 'replace' if b is rep else 'keepboth' if b is keep else 'skip' if b is skip else None
 def _cancel_visible_transfer(self):
  worker=self._visible_transfer
  if worker in self.operations:
   worker.cancel(); self.transfer_title.setText('Cancelling…'); self.transfer_cancel.setEnabled(False)
 def _render_transfer(self,worker):
  state=self._transfer_states.get(worker)
  if not state:return
  self._visible_transfer=worker; self.transfer_bar.show(); self.transfer_cancel.setEnabled(not worker.cancelled)
  count=len(self.operations); prefix=f'{count} transfers · ' if count>1 else ''
  self.transfer_title.setText(prefix+state['title'])
  bd,bt=state.get('bytes_done',0),state.get('bytes_total',0)
  if bt>0:
   self.progress.setRange(0,1000); self.progress.setValue(min(1000,int(bd*1000/bt)))
   detail=f"{state.get('name','')} · {human(bd)} / {human(bt)}"
   rate=state.get('rate',0)
   if rate>0:
    detail+=f' · {human(rate)}/s'
    remain=max(0,bt-bd); eta=remain/rate if rate else 0
    if eta>=1:detail+=f' · ~{int(eta)} s left'
  else:
   done,total=state.get('done',0),state.get('total',1); self.progress.setRange(0,max(1,total)); self.progress.setValue(done); detail=f"{done}/{total} · {state.get('name','')}"
  self.transfer_detail.setText(detail.strip(' ·'))
 def _finish_transfer_ui(self,worker,message,error=False):
  self._transfer_states.pop(worker,None)
  if worker in self.operations:self.operations.remove(worker)
  if self.operations:
   self._render_transfer(self.operations[-1])
  else:
   self._visible_transfer=None; self.transfer_bar.hide()
   if self._close_after_transfers:QTimer.singleShot(0,self.close)
  if not error:self.status.setText(message)
 def start_transfer(self,items,dst,move=False,source_label=None,dest_label=None):
  items=[Path(x) for x in items]; dst=Path(dst)
  if not items:return
  # Conflict discovery is metadata I/O and may hit FUSE. Always perform it away from the GUI thread.
  payload=[]
  for x in items:
   target=dst/x.name; payload.append(self._path_endpoint_meta(target))
  self.status.setText('Checking destination…')
  worker=MetadataWorker('conflicts',payload)
  def ready(r):
   if not self._accept_worker_results:return
   conflicts=r.get('conflicts',[]); policy=self.choose_conflict_policy(conflicts,dst)
   if policy is None:self.update_status(); return
   self._start_transfer_ready(items,dst,move,source_label,dest_label,policy)
  worker.signals.done.connect(ready); worker.signals.failed.connect(lambda e:self.err('Could not inspect destination safely: '+str(e))); self._start_worker(self._remote_probe_pool,worker)
 def _start_transfer_ready(self,items,dst,move=False,source_label=None,dest_label=None,policy='ask'):
  items=[Path(x) for x in items]; dst=Path(dst)
  if not items:return
  # Local-only free-space preflight. Remote/FUSE capacity checks must never block the GUI thread.
  if not self._remote_path(dst) and all(not self._remote_path(x) for x in items):
   try:
    required=sum(x.stat().st_size for x in items if x.is_file()); free=shutil.disk_usage(dst if dst.exists() else dst.parent).free
    if required and required>free:return self.err(f'Not enough free space.\n\nRequired: {human(required)}\nAvailable: {human(free)}')
   except OSError:pass
  worker=TransferWorker(items,dst,move,policy); self.operations.append(worker); route=f'{source_label} → {dest_label}' if source_label and dest_label else str(dst); verb='Moving' if move else 'Copying'
  state={'title':f'{verb} {len(items)} item(s) · {route}','done':0,'total':max(1,len(items)),'name':'Preparing…','bytes_done':0,'bytes_total':0,'sample_t':time.monotonic(),'sample_b':0,'rate':0.0}; self._transfer_states[worker]=state; self._render_transfer(worker)
  def transfer_progress(done,total,name):
   state.update(done=done,total=max(1,total),name=name)
   if state.get('bytes_total',0)<=0:self._render_transfer(worker)
  def activity(info):
   now=time.monotonic(); bd=int(info.get('bytes_done',0)); bt=int(info.get('bytes_total',0)); name=info.get('name','')
   if name!=state.get('byte_name'):
    state.update(byte_name=name,sample_t=now,sample_b=bd,rate=0.0)
   else:
    dt=now-state.get('sample_t',now); delta=bd-state.get('sample_b',bd)
    if dt>=0.25 and delta>=0:
     instant=delta/dt; old=state.get('rate',0.0); state['rate']=instant if old<=0 else old*.65+instant*.35; state['sample_t']=now; state['sample_b']=bd
   state.update(name=name,bytes_done=bd,bytes_total=bt); self._render_transfer(worker)
  worker.signals.progress.connect(transfer_progress); worker.signals.activity.connect(activity)
  def done(result):
   changes=result.get('changes',[])
   if changes:self.undo_stack.append(changes)
   self._finish_transfer_ui(worker,result.get('message','Operation complete')); QTimer.singleShot(4000,self.update_status)
  def failed(msg):
   self._finish_transfer_ui(worker,'Transfer failed',True); self.status.setText('Transfer failed · '+str(msg)); self.err(msg)
  worker.signals.done.connect(done); worker.signals.failed.connect(failed); self._start_worker(self.threadpool,worker)
 def undo_last(self):
  if not self.undo_stack:return self.status.setText('Nothing to undo')
  changes=self.undo_stack[-1]
  if any(c.get('replaced') for c in changes):return self.err('Undo cannot safely restore overwritten originals. The new files have been kept.')
  if any(self._remote_path(c['src']) or self._remote_path(c['dst']) for c in changes):return self.err('Remote undo is unavailable: use an explicit reverse transfer instead.')
  self.undo_stack.pop()
  try:
   for c in reversed(changes):
    src,dst=Path(c['src']),Path(c['dst'])
    if c.get('move'):
     if dst.exists() and not src.exists():src.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(dst),str(src))
    else:
     if dst.is_dir() and not dst.is_symlink():shutil.rmtree(dst)
     elif dst.exists() or dst.is_symlink():dst.unlink()
   self.status.setText('Last transfer undone')
  except Exception as e:self.err(f'Undo could not be completed safely: {e}')
 def save_collection(self):
  items=self.selected()
  if not items:return self.err('Select one or more files first.')
  name,ok=QInputDialog.getText(self,'New Collection','Name:')
  if not ok or not name.strip():return
  data=self.s.value('collections_json','{}') or '{}'
  try:cols=json.loads(data)
  except:cols={}
  cols[name.strip()]=[str(p) for p in items]; self.s.setValue('collections_json',json.dumps(cols)); self.status.setText(f'Collection saved · {name.strip()}')
 def open_collection(self):
  try:cols=json.loads(self.s.value('collections_json','{}') or '{}')
  except:cols={}
  if not cols:return self.err('No Collections saved yet.')
  name,ok=QInputDialog.getItem(self,'Collections','Collection:',sorted(cols),0,False)
  if not ok:return
  d=NiruDialog(self); d.setWindowTitle(f'Collection — {name}'); d.resize(700,500); l=QVBoxLayout(d); w=QListWidget()
  for x in cols[name]:
   p=Path(x); meta=self._path_endpoint_meta(x); it=QListWidgetItem(f'{p.name or x}   ·   {meta.get("endpoint","Local")}'); it.setToolTip(str(p)); it.setData(Qt.ItemDataRole.UserRole,x); w.addItem(it)
  def op(it):
   p=Path(it.data(Qt.ItemDataRole.UserRole)); self.active.go(p.parent)
  w.itemDoubleClicked.connect(op); l.addWidget(w); d.exec()
 def _json_setting(self,key):
  try:return json.loads(self.s.value(key,'{}') or '{}')
  except:return {}
 def _save_json(self,key,data):self.s.setValue(key,json.dumps(data,ensure_ascii=False))
 def manage_targets(self):
  data=self._json_setting('targets_json'); d=NiruDialog(self); d.setWindowTitle('Locations'); d.resize(620,430); l=QVBoxLayout(d); w=QListWidget()
  def refresh():
   w.clear()
   for n,p in sorted(data.items()):
    it=QListWidgetItem(f'{n}   ·   {p}'); it.setData(Qt.ItemDataRole.UserRole,n); w.addItem(it)
  refresh(); l.addWidget(QLabel('Saved locations for fast navigation and Send to actions. Locations are intentionally lightweight.')); l.addWidget(w,1); row=QHBoxLayout(); add=QPushButton('Add'); rem=QPushButton('Remove'); op=QPushButton('Open'); row.addWidget(add); row.addWidget(rem); row.addStretch(); row.addWidget(op); l.addLayout(row)
  def addone():
   p=QFileDialog.getExistingDirectory(d,'Target folder',str(Path.home()))
   if not p:return
   n,ok=QInputDialog.getText(d,'Target','Name:',text=Path(p).name)
   if ok and n.strip():data[n.strip()]=p; self._save_json('targets_json',data); refresh()
  def remove():
   it=w.currentItem()
   if it:data.pop(it.data(Qt.ItemDataRole.UserRole),None); self._save_json('targets_json',data); refresh()
  def openit():
   it=w.currentItem()
   if it:self.active.go(data[it.data(Qt.ItemDataRole.UserRole)]); d.accept()
  add.clicked.connect(addone); rem.clicked.connect(remove); op.clicked.connect(openit); w.itemDoubleClicked.connect(lambda *_:openit()); d.exec()
 def send_target(self):
  items=self.selected(); data=self._json_setting('targets_json')
  if not items:return self.err('Select one or more items first.')
  if not data:return self.manage_targets()
  n,ok=QInputDialog.getItem(self,'Send to Target','Target:',sorted(data),0,False)
  if ok:self.start_transfer(items,Path(data[n]),False)
 def open_workspace_named(self,name):
  ws=self._json_setting('workspaces_json').get(name)
  if not ws:return self.err('Workspace no longer exists.')
  left=ws.get('left'); right=ws.get('right'); split=bool(ws.get('split',bool(right)))
  if ws.get('left_tabs'):self.pane1.restore_tabs(ws['left_tabs'])
  elif left:self.pane1.go(left)
  if split:
   self._show_right_pane(empty=True); self.pane2.restore_tabs(ws['right_tabs']) if ws.get('right_tabs') else self.pane2._insert_tab_state({'path':right if right else str(Path.home()),'history':[],'hist':-1,'pinned':False})
   if ws.get('split_sizes'):self.split.setSizes([int(x) for x in ws['split_sizes']])
  elif not split:self.pane2.hide()
  active=self.pane2 if ws.get('active')=='right' and self.pane2.isVisible() else self.pane1; self.set_active(active)
  if ws.get('quicklook',False):self.quickdock.show()
  else:self.quickdock.hide()
  self.update_status(); self.status.setText(f'Workspace restored · {name}')
 def manage_workspaces(self):
  data=self._json_setting('workspaces_json'); d=NiruDialog(self); d.setWindowTitle('Workspace Snapshots'); d.resize(760,500); l=QVBoxLayout(d); w=QListWidget()
  def refresh():
   w.clear()
   for n,v in sorted(data.items()):
    right=v.get('right','') if v.get('split',bool(v.get('right'))) else 'single pane'; it=QListWidgetItem(f'{n}   ·   {v.get("left","")}   ↔   {right}'); it.setData(Qt.ItemDataRole.UserRole,n); w.addItem(it)
  refresh(); info=QLabel('Snapshots restore pane locations, split state, active pane and Quick Look. They do not start background services or alter files.'); info.setWordWrap(True); l.addWidget(info); l.addWidget(w,1); row=QHBoxLayout(); save=QPushButton('Save current'); replace=QPushButton('Update'); rename=QPushButton('Rename'); duplicate=QPushButton('Duplicate'); rem=QPushButton('Remove'); op=QPushButton('Open'); row.addWidget(save); row.addWidget(replace); row.addWidget(rename); row.addWidget(duplicate); row.addWidget(rem); row.addStretch(); row.addWidget(op); l.addLayout(row)
  def snapshot():return {'left':str(self.pane1.current),'right':str(self.pane2.current) if self.pane2.isVisible() else '','left_tabs':self.pane1.export_tabs(),'right_tabs':self.pane2.export_tabs(),'split':self.pane2.isVisible(),'active':'right' if self.active is self.pane2 else 'left','quicklook':self.quickdock.isVisible(),'split_sizes':self.split.sizes()}
  def savecur():
   n,ok=QInputDialog.getText(d,'Workspace Snapshot','Name:')
   if ok and n.strip():data[n.strip()]=snapshot(); self._save_json('workspaces_json',data); refresh(); self.build_sidebar()
  def chosen():return w.currentItem().data(Qt.ItemDataRole.UserRole) if w.currentItem() else None
  def updatecur():
   n=chosen()
   if n:data[n]=snapshot(); self._save_json('workspaces_json',data); refresh(); self.status.setText(f'Workspace updated · {n}')
  def renameone():
   n=chosen()
   if not n:return
   new,ok=QInputDialog.getText(d,'Rename Workspace','Name:',text=n)
   if ok and new.strip() and new.strip()!=n:
    if new.strip() in data:return self.err('A workspace with that name already exists.')
    data[new.strip()]=data.pop(n); self._save_json('workspaces_json',data); refresh(); self.build_sidebar()
  def duplicateone():
   n=chosen()
   if not n:return
   new,ok=QInputDialog.getText(d,'Duplicate Workspace','Name:',text=n+' copy')
   if ok and new.strip():
    if new.strip() in data:return self.err('A workspace with that name already exists.')
    data[new.strip()]=dict(data[n]); self._save_json('workspaces_json',data); refresh(); self.build_sidebar()
  def remove():
   n=chosen()
   if n and self.confirm('Remove Workspace',f'Remove workspace snapshot “{n}”?\n\nNo files or folders will be deleted.','Remove'):
    data.pop(n,None); self._save_json('workspaces_json',data); refresh(); self.build_sidebar()
  def openit():
   n=chosen()
   if n:d.accept(); self.open_workspace_named(n)
  save.clicked.connect(savecur); replace.clicked.connect(updatecur); rename.clicked.connect(renameone); duplicate.clicked.connect(duplicateone); rem.clicked.connect(remove); op.clicked.connect(openit); w.itemDoubleClicked.connect(lambda *_:openit()); d.exec()
 def open_server_named(self,name,other_pane=False):
  data=self._json_setting('servers_json'); v=data.get(name)
  if not v:return self.err(f'Connection “{name}” no longer exists.')
  safe=''.join(c if c.isalnum() or c in '-_.' else '_' for c in name); mp=Path.home()/'.local/share/niruorg/mounts'/safe
  source=self.active; target=source
  if other_pane:
   target=self.pane2 if source is self.pane1 else self.pane1
   if self.pane2.isHidden():self.toggle_split()
  self.set_active(target)
  if path_is_mounted(mp):
   target.bind_remote(name,v.get('protocol','sftp'),mp,v.get('path','/')); target.go(str(mp)); return
  self.manage_servers(name,'connect',target)
 def _store_imported_server_secret(self,name,cfg,password):
  if not password:return True
  exe=shutil.which('secret-tool')
  if not exe:return False
  attrs=['application','niruorg','service','server','server',name,'user',cfg.get('user','')]
  try:
   r=subprocess.run([exe,'store','--label=NIRUORG server '+name]+attrs,input=password+'\n',text=True,capture_output=True,timeout=8)
   return r.returncode==0
  except Exception:return False

 def _filezilla_sites(self,path):
  root=ET.parse(path).getroot(); out=[]
  for node in root.findall('.//Server'):
   def val(tag,default=''):
    x=node.find(tag); return (x.text or '').strip() if x is not None else default
   host=val('Host'); name=val('Name') or host
   if not host:continue
   try:proto_num=int(val('Protocol','0'))
   except:proto_num=0
   proto={0:'ftp',1:'sftp',3:'ftps-implicit',4:'ftps'}.get(proto_num,'sftp' if proto_num==1 else 'ftp')
   try:port=int(val('Port',str(22 if proto=='sftp' else 21)))
   except:port=22 if proto=='sftp' else 21
   user=val('User'); raw=val('Pass'); enc=(node.find('Pass').attrib.get('encoding','') if node.find('Pass') is not None else '')
   password=''
   if raw:
    try:password=base64.b64decode(raw).decode() if enc=='base64' else raw
    except Exception:password=''
   remote=val('RemoteDir','/') or '/'
   # FileZilla's RemoteDir may use an internal tokenized format; only keep normal absolute paths.
   if not remote.startswith('/'):remote='/'
   out.append({'name':name,'password':password,'cfg':{'protocol':proto,'route':'direct','host':host,'user':user,'port':port,'path':remote,'auth':'password' if password or proto!='sftp' else 'auto','key':'','remember_password':bool(password),'timeout':12,'proxyjump':'','keepalive':15,'passive':True,'tls_verify':True,'advanced':False}})
  return out

 def _openssh_sites(self,path):
  out=[]; cur=None
  try:lines=Path(path).read_text(errors='replace').splitlines()
  except Exception:return out
  for raw in lines:
   line=raw.strip()
   if not line or line.startswith('#'):continue
   parts=line.split(None,1)
   if len(parts)<2:continue
   k,v=parts[0].lower(),parts[1].strip()
   if k=='host':
    if cur and cur['name'] and '*' not in cur['name'] and '?' not in cur['name']:out.append(cur)
    cur={'name':v.split()[0],'password':'','cfg':{'protocol':'sftp','route':'direct','host':v.split()[0],'user':'','port':22,'path':'/','auth':'auto','key':'','remember_password':False,'timeout':12,'proxyjump':'','keepalive':15,'passive':True,'tls_verify':True,'advanced':False}}
   elif cur:
    c=cur['cfg']
    if k=='hostname':c['host']=v
    elif k=='user':c['user']=v
    elif k=='port':
     try:c['port']=int(v)
     except:pass
    elif k=='identityfile':c['auth']='key'; c['key']=v
    elif k=='proxyjump':c['proxyjump']=v
  if cur and cur['name'] and '*' not in cur['name'] and '?' not in cur['name']:out.append(cur)
  return out

 def import_connections(self):
  d=NiruDialog(self); d.setWindowTitle('Import Connections'); d.resize(780,560); l=QVBoxLayout(d)
  intro=QLabel('<b>Import connections</b><br>Import selected sites into NIRUORG. Existing connections are never overwritten silently. FileZilla passwords can be imported into Linux Secret Service; they are not written to NIRUORG settings. Proton Pass is optional and is not required for imports or normal operation.'); intro.setWordWrap(True); l.addWidget(intro)
  tree=QTreeWidget(); tree.setHeaderLabels(['Import','Name','Protocol','Endpoint','Credential']); tree.setRootIsDecorated(False); l.addWidget(tree,1)
  found=[]
  def load(items,source):
   nonlocal found; found=[]; tree.clear()
   for x in items:
    x['source']=source; found.append(x); c=x['cfg']; it=QTreeWidgetItem(['✓',x['name'],c['protocol'].upper(),f'{c.get("user","")+"@" if c.get("user") else ""}{c["host"]}:{c["port"]}','Password' if x.get('password') else ('SSH key' if c.get('key') else 'OpenSSH / Auto')]); it.setCheckState(0,Qt.CheckState.Checked); tree.addTopLevelItem(it)
   status.setText(f'{len(found)} connection(s) found · choose the entries to import')
  def filezilla():
   candidates=[Path.home()/'.config/filezilla/sitemanager.xml',Path.home()/'.filezilla/sitemanager.xml']
   start=str(next((x for x in candidates if x.exists()),Path.home()))
   fn,_=QFileDialog.getOpenFileName(d,'Choose FileZilla sitemanager.xml',start,'FileZilla XML (*.xml);;All files (*)')
   if fn:
    try:load(self._filezilla_sites(fn),'FileZilla')
    except Exception as e:self.err('Could not read FileZilla XML.\n\n'+str(e))
  def openssh():
   fn,_=QFileDialog.getOpenFileName(d,'Choose OpenSSH config',str(Path.home()/'.ssh/config'),'SSH config (*)')
   if fn:load(self._openssh_sites(fn),'OpenSSH')
  def doimport():
   data=self._json_setting('servers_json'); added=0; secrets=0; skipped=0
   for i,x in enumerate(found):
    if tree.topLevelItem(i).checkState(0)!=Qt.CheckState.Checked:continue
    name=x['name']; base=name; n=2
    while name in data:name=f'{base} {n}'; n+=1
    cfg=dict(x['cfg']); pw=x.get('password','')
    if pw:
     if shutil.which('secret-tool'):
      cfg['remember_password']=True
      if self._store_imported_server_secret(name,cfg,pw):secrets+=1
      else:cfg['remember_password']=False
     else:cfg['remember_password']=False
    data[name]=cfg; added+=1
   self._save_json('servers_json',data); self.build_sidebar(); status.setText(f'Imported {added} connection(s) · {secrets} password(s) stored in Secret Service');
   if added:self.info('Import complete',f'Imported {added} connection(s).\n\nPasswords stored securely: {secrets}.\nExisting connections were preserved; duplicate names were renamed.')
  buttons=QHBoxLayout(); fz=QPushButton('FileZilla XML…'); ssh=QPushButton('OpenSSH config…'); imp=QPushButton('Import selected'); close=QPushButton('Close'); buttons.addWidget(fz); buttons.addWidget(ssh); buttons.addStretch(); buttons.addWidget(imp); buttons.addWidget(close); l.addLayout(buttons); status=QLabel('Choose an import source.'); status.setObjectName('muted'); l.addWidget(status); fz.clicked.connect(filezilla); ssh.clicked.connect(openssh); imp.clicked.connect(doimport); close.clicked.connect(d.reject); d.exec()

 def package_inspector(self):
  sel=self.selected(); p=sel[0] if len(sel)==1 and sel[0].is_file() else None
  if not p:
   fn,_=QFileDialog.getOpenFileName(self,'Inspect package',str(self.current_dir()),'Archives (*.zip *.tar *.tar.gz *.tgz *.tar.xz *.txz);;All files (*)'); p=Path(fn) if fn else None
  if not p:return
  try:
   names=[]; unpacked=0
   if zipfile.is_zipfile(p):
    with zipfile.ZipFile(p) as z:
     bad=z.testzip(); infos=z.infolist(); names=[x.filename for x in infos]; unpacked=sum(x.file_size for x in infos); valid='Yes' if bad is None else 'No · corrupt member '+str(bad)
   elif tarfile.is_tarfile(p):
    with tarfile.open(p) as t:infos=t.getmembers(); names=[x.name for x in infos]; unpacked=sum(x.size for x in infos if x.isfile()); valid='Yes'
   else:return self.err('Unsupported or invalid archive.')
   roots=sorted({n.strip('/').split('/')[0] for n in names if n.strip('/')}); rootlabel=roots[0]+'/' if len(roots)==1 else f'{len(roots)} top-level entries'; root_ok=len(roots)==1; expected=re.sub(r'\.(zip|tar|tar\.gz|tgz|tar\.xz|txz)$','',p.name,flags=re.I); root_match=root_ok and roots[0]==expected; required_names={Path(n).name for n in names}; release_checks=[('Single root directory',root_ok),('Root matches package name',root_match),('README.md present','README.md' in required_names),('CHANGELOG.md present','CHANGELOG.md' in required_names),('install.sh present','install.sh' in required_names)]
   h=hashlib.sha256();
   with p.open('rb') as f:
    for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
   digest=h.hexdigest(); checks='<br>'.join(('✓ ' if ok else '– ')+name for name,ok in release_checks); text=f'<b>{p.name}</b><br><br>Archive valid: {valid}<br>Root: {rootlabel}<br>{checks}<br>Entries: {len(names)}<br>Compressed: {human(p.stat().st_size)}<br>Unpacked: {human(unpacked)}<br><br><b>SHA-256</b><br><tt>{digest}</tt>'
   d=NiruDialog(self); d.setWindowTitle('Package Inspector'); d.resize(650,400); l=QVBoxLayout(d); lab=QLabel(text); lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); lab.setWordWrap(True); l.addWidget(lab); l.addStretch(); row=QHBoxLayout(); cp=QPushButton('Copy SHA-256'); browse=QPushButton('Browse archive'); close=QPushButton('Close'); row.addWidget(cp); row.addWidget(browse); row.addStretch(); row.addWidget(close); l.addLayout(row); cp.clicked.connect(lambda:QApplication.clipboard().setText(digest)); browse.clicked.connect(lambda:(d.accept(),self.archive_browser())); close.clicked.connect(d.accept); d.exec()
  except Exception as e:self.err('Package inspection failed.\n\n'+str(e))

 def system_diagnostics(self):
  rows=[]
  rows.append(('NIRUORG',VERSION,'Application version'))
  rows.append(('Python',sys.version.split()[0],sys.executable))
  rows.append(('Qt / PySide6',qVersion(),'Runtime'))
  rows.append(('Session',os.getenv('XDG_SESSION_TYPE','unknown'),os.getenv('XDG_CURRENT_DESKTOP','') or '—'))
  for label,path in self.integration_status():rows.append((label,'Available' if path else 'Optional / unavailable',str(path or '—')))
  servers=self._json_setting('servers_json'); rows.append(('Tabs',f'{self.pane1.tabs.count()} left · {self.pane2.tabs.count()} right','Per-pane tab workspaces')); rows.append(('Resumable transfers','Available','.niruorg-part files are retained after cancellation')); rows.append(('Connections',str(len(servers)),f'{sum(1 for n in servers if path_is_mounted(Path.home()/".local/share/niruorg/mounts"/"".join(c if c.isalnum() or c in "-_ ." else "_" for c in n)))} mounted'))
  d=NiruDialog(self); d.setWindowTitle('System Diagnostics'); d.resize(780,560); l=QVBoxLayout(d); note=QLabel('<b>Safe diagnostic report</b><br>No passwords, tokens, private keys or Secret Service values are included.'); note.setWordWrap(True); l.addWidget(note); t=QTreeWidget(); t.setHeaderLabels(['Component','Status','Details']); t.setRootIsDecorated(False); l.addWidget(t,1)
  for a,b,c in rows:QTreeWidgetItem(t,[a,b,c])
  t.header().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); t.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents); t.header().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
  def copy():QApplication.clipboard().setText('\n'.join(f'{a}: {b} · {c}' for a,b,c in rows)); self.status.setText('Diagnostic report copied · secrets excluded')
  row=QHBoxLayout(); cp=QPushButton('Copy diagnostic report'); close=QPushButton('Close'); row.addWidget(cp); row.addStretch(); row.addWidget(close); l.addLayout(row); cp.clicked.connect(copy); close.clicked.connect(d.accept); d.exec()

 def manage_servers(self,initial_name=None,initial_action=None,target_pane=None):
  target_pane=target_pane or self.active
  data=self._json_setting('servers_json'); d=NiruDialog(self); d.setWindowTitle('Connections'); d.resize(900,620); l=QVBoxLayout(d)
  info=QLabel('<b>Connections</b><br>Add a server once, then click it in the sidebar whenever you want to browse it. SFTP is recommended for SSH-capable servers. Tailscale works with the same SFTP/SSH connection using a MagicDNS name or 100.x address.'); info.setWordWrap(True); l.addWidget(info)
  w=QListWidget(); l.addWidget(w,1); status=QLabel('Ready'); status.setWordWrap(True); status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); l.addWidget(status)
  row=QHBoxLayout(); add=QPushButton('Add connection'); importb=QPushButton('Import…'); edit=QPushButton('Edit…'); clone=QPushButton('Duplicate…'); rem=QPushButton('Remove…'); test=QPushButton('Test'); diagnose=QPushButton('Diagnose…'); details=QPushButton('Details'); unlock=QPushButton('Unlock SSH key…'); ssh=QPushButton('SSH terminal'); disconnect=QPushButton('Disconnect'); connect=QPushButton('Connect / Browse'); cancel=QPushButton('Cancel operation'); cancel.setObjectName('cancelOperation'); cancel.setEnabled(False); close=QPushButton('Close'); close.clicked.connect(d.reject)
  for x in (add,importb,edit,clone,rem):row.addWidget(x)
  row.addStretch()
  for x in (test,diagnose,details,unlock,ssh,disconnect,connect,cancel,close):row.addWidget(x)
  l.addLayout(row)
  state={'proc':None,'timer':None,'action':'','name':'','mount':None,'tmp':None,'retry':None}; session_passwords={}
  def safe_name(n):return ''.join(c if c.isalnum() or c in '-_.' else '_' for c in n)
  def mountpoint(n):return Path.home()/'.local/share/niruorg/mounts'/safe_name(n)
  def protocol(v):return v.get('protocol','sftp').lower()
  def auth(v):return v.get('auth','auto').lower()
  def refresh(select=None):
   w.clear()
   for n,v in sorted(data.items()):
    mounted=path_is_mounted(mountpoint(n)); mark='●' if mounted else '○'; proto=protocol(v).upper(); av=auth(v); al={'auto':'OpenSSH / Auto','key':'SSH key','password':'Password'}.get(av,av)
    route={'direct':'Direct','tailscale':'Tailscale','tailscale-ssh':'Tailscale SSH'}.get(v.get('route','direct'),'Direct'); endpoint=(f'{v.get("user")}@' if v.get('user') else '')+f'{v.get("host","")}:{v.get("port",22)}'; it=QListWidgetItem(f'{mark}  {n}    {proto} · {route}    {endpoint}    {al}'); it.setData(Qt.ItemDataRole.UserRole,n); it.setToolTip(f'{proto} · {route}\n{endpoint}\nRemote folder: {v.get("path","/")}\nAuthentication: {al}'); w.addItem(it)
    if select==n:w.setCurrentItem(it)
  def current():
   it=w.currentItem(); n=it.data(Qt.ItemDataRole.UserRole) if it else None; return (n,data.get(n)) if n else (None,None)
  def update_actions():
   n,v=current(); has=bool(v); busy=bool(state.get('proc'))
   for b in (edit,clone,rem,test,diagnose,details,unlock,ssh,disconnect,connect):b.setEnabled(has and not busy)
   if v:
    ssh.setEnabled(not busy and protocol(v)=='sftp'); unlock.setEnabled(not busy and protocol(v)=='sftp' and auth(v) in ('auto','key'))
   if not data and not busy:status.setText('No connections yet · choose Add connection to create one.')
  def set_busy(on,msg=''):
   add.setEnabled(not on); close.setEnabled(not on); cancel.setEnabled(on); w.setEnabled(not on)
   if on:
    for x in (edit,clone,rem,test,diagnose,details,unlock,ssh,disconnect,connect):x.setEnabled(False)
   else:update_actions()
   if msg:status.setText(msg)
  def server_editor(title,original=None,suggested=''):
   v=dict(original or {}); box=NiruDialog(d); box.setWindowTitle(title); box.setModal(True); box.resize(680,640); outer=QVBoxLayout(box)
   intro=QLabel('<b>Remote connection</b><br>Choose the protocol first. For a Linux server, use SFTP / SSH. For a hosting account, use the protocol and hostname supplied by the provider. Only settings relevant to your choice are shown.'); intro.setWordWrap(True); outer.addWidget(intro)
   f=QFormLayout(); outer.addLayout(f)
   name=QLineEdit(suggested); proto=QComboBox(); proto.addItems(['SFTP / SSH (recommended)','FTP','FTPS · explicit TLS','FTPS · implicit TLS'])
   pv=protocol(v); proto.setCurrentIndex({'sftp':0,'ftp':1,'ftps':2,'ftps-implicit':3}.get(pv,0))
   route=QComboBox(); route.addItems(['Direct / LAN / Internet','Tailscale · MagicDNS / 100.x IP','Tailscale SSH'])
   route.setCurrentIndex({'direct':0,'tailscale':1,'tailscale-ssh':2}.get(v.get('route','direct'),0))
   host=QLineEdit(v.get('host','')); host.setPlaceholderText('nas.example.net, 100.x.x.x, ftp.example.net …')
   user=QLineEdit(v.get('user',os.getenv('USER',''))); port=QSpinBox(); port.setRange(1,65535); port.setValue(int(v.get('port',22 if pv in ('ssh','sftp') else (990 if pv=='ftps-implicit' else 21)))); path=QLineEdit(v.get('path','/')); path.setPlaceholderText('/home/user or /')
   am=QComboBox(); am.addItems(['OpenSSH / Auto (recommended)','SSH key','Password']); amap={'auto':0,'key':1,'password':2}; am.setCurrentIndex(amap.get(auth(v),0)); key=QLineEdit(v.get('key','')); key.setPlaceholderText('Optional private key, e.g. ~/.ssh/id_ed25519'); browsekey=QPushButton('Browse…'); kh=QHBoxLayout(); kh.addWidget(key,1); kh.addWidget(browsekey); kw=QWidget(); kw.setLayout(kh)
   remember=QCheckBox('Remember password securely in Linux Secret Service'); remember.setChecked(bool(v.get('remember_password',False))); timeout=QSpinBox(); timeout.setRange(3,120); timeout.setValue(int(v.get('timeout',12))); timeout.setSuffix(' s')
   advanced=QGroupBox('Advanced'); advanced.setCheckable(True); advanced.setChecked(bool(v.get('advanced',False) or v.get('proxyjump'))); af=QFormLayout(advanced); proxy=QLineEdit(v.get('proxyjump','')); proxy.setPlaceholderText('Optional SSH jump host / ProxyJump'); keep=QSpinBox(); keep.setRange(0,300); keep.setValue(int(v.get('keepalive',15))); keep.setSuffix(' s'); passive=QCheckBox('Passive FTP mode (required by rclone)'); passive.setChecked(True); passive.setEnabled(False); tlsverify=QCheckBox('Verify TLS certificate'); tlsverify.setChecked(bool(v.get('tls_verify',True))); af.addRow('ProxyJump',proxy); af.addRow('Keepalive',keep); af.addRow('',passive); af.addRow('',tlsverify)
   f.addRow('Connection name',name); f.addRow('Protocol',proto); f.addRow('Network route',route); f.addRow('Host / MagicDNS / IP',host); f.addRow('Username',user); f.addRow('Port',port); f.addRow('Start folder',path); f.addRow('Authentication',am); f.addRow('SSH identity',kw); f.addRow('',remember); f.addRow('Timeout',timeout); outer.addWidget(advanced)
   hint=QLabel('<b>Recommended:</b> SFTP + OpenSSH / Auto lets your existing ~/.ssh/config, ssh-agent and standard keys work without configuring a key twice. For a server over Tailscale, select Tailscale and use its MagicDNS hostname or 100.x address.'); hint.setWordWrap(True); outer.addWidget(hint)
   browsekey.clicked.connect(lambda: key.setText(QFileDialog.getOpenFileName(box,'Choose SSH private key',str(Path.home()/'.ssh'))[0] or key.text()))
   def defaults():
    i=proto.currentIndex(); defaults=[22,21,21,990]; old=port.value()
    if old in (21,22,990):port.setValue(defaults[i])
   def sync():
    sshish=proto.currentIndex()==0; am.setVisible(sshish); kw.setVisible(sshish and am.currentIndex()==1); remember.setVisible((sshish and am.currentIndex()==2) or not sshish); proxy.setVisible(sshish); keep.setVisible(sshish); passive.setVisible(not sshish); tlsverify.setVisible(proto.currentIndex() in (2,3))
    for layout,field,visible in ((f,am,sshish),(f,kw,sshish and am.currentIndex()==1),(af,proxy,sshish),(af,keep,sshish),(af,passive,not sshish),(af,tlsverify,proto.currentIndex() in (2,3))):
     label=layout.labelForField(field)
     if label is not None:label.setVisible(visible)
    if not sshish and am.currentIndex()!=2:am.setCurrentIndex(2)
    if route.currentIndex()==2 and not sshish:route.setCurrentIndex(0)
   proto.currentIndexChanged.connect(defaults); proto.currentIndexChanged.connect(sync); am.currentIndexChanged.connect(sync); route.currentIndexChanged.connect(sync); sync()
   bb=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); saveconnect=bb.addButton('Save & connect',QDialogButtonBox.ButtonRole.ActionRole); box.setProperty('save_and_connect',False); saveconnect.clicked.connect(lambda: (box.setProperty('save_and_connect',True),box.accept())); bb.accepted.connect(box.accept); bb.rejected.connect(box.reject); outer.addWidget(bb)
   name.setFocus()
   if box.exec()!=QDialog.DialogCode.Accepted:return None
   n=name.text().strip(); h=host.text().strip(); u=user.text().strip()
   if not n or not h:self.err('Name and host are required.'); return None
   pr=['sftp','ftp','ftps','ftps-implicit'][proto.currentIndex()]; au=['auto','key','password'][am.currentIndex()] if pr=='sftp' else 'password'; rt=['direct','tailscale','tailscale-ssh'][route.currentIndex()]
   if rt=='tailscale-ssh' and pr!='sftp':self.err('Tailscale SSH is only available with SFTP / SSH.'); return None
   if pr=='sftp' and au=='key' and not key.text().strip():self.err('SSH key is selected, but no private key file is configured. Choose a key, or use OpenSSH / Auto to use ssh-agent, ~/.ssh/config and standard keys.'); return None
   return n,{'protocol':pr,'route':rt,'host':h,'user':u,'port':port.value(),'path':path.text().strip() or '/','auth':au,'key':key.text().strip() if au=='key' else '','remember_password':bool(remember.isChecked() and au=='password'),'timeout':timeout.value(),'proxyjump':proxy.text().strip(),'keepalive':keep.value(),'passive':passive.isChecked(),'tls_verify':tlsverify.isChecked(),'advanced':advanced.isChecked()},bool(box.property('save_and_connect'))
  def secret_key(n,v):return ['application','niruorg','service','server','server',n,'user',v.get('user','')]
  def secret_lookup(n,v):
   if n in session_passwords:return session_passwords[n]
   if not v.get('remember_password') or not shutil.which('secret-tool'):return ''
   try:
    r=subprocess.run(['secret-tool','lookup']+secret_key(n,v),capture_output=True,text=True,timeout=4); return r.stdout.rstrip('\n') if r.returncode==0 else ''
   except Exception:return ''
  def secret_store(n,v,pw):
   session_passwords[n]=pw
   if not v.get('remember_password'):return True
   if not shutil.which('secret-tool'):self.err('Secret Service is unavailable. The password will be kept for this NIRUORG session only.'); return False
   try:
    r=subprocess.run(['secret-tool','store','--label=NIRUORG server '+n]+secret_key(n,v),input=pw+'\n',text=True,capture_output=True,timeout=5); return r.returncode==0
   except Exception:return False
  def secret_clear(n,v):
   session_passwords.pop(n,None)
   if shutil.which('secret-tool'):
    try:subprocess.run(['secret-tool','clear']+secret_key(n,v),capture_output=True,timeout=4)
    except Exception:pass
  def get_password(n,v):
   pw=secret_lookup(n,v)
   if pw:return pw
   pw,ok=QInputDialog.getText(d,'Password · '+n,f'Password for {v.get("user","")}@{v.get("host","")}:',QLineEdit.EchoMode.Password)
   if not ok:return None
   secret_store(n,v,pw); return pw
  def save_entry(result,old=None):
   if not result:return
   n,v,*extra=result; connect_after=bool(extra[0]) if extra else False
   if n!=old and n in data:return self.err(f'A server named {n} already exists.')
   if old and old!=n:
    oldv=data.get(old,{}) ; data.pop(old,None); session_passwords.pop(old,None)
    if oldv.get('remember_password'):secret_clear(old,oldv)
   data[n]=v; self._save_json('servers_json',data); refresh(n); self.build_sidebar(); QTimer.singleShot(0,connectone) if connect_after else None
  def addone():
   status.setText('Opening connection editor…')
   try:
    result=server_editor('Add connection')
    if result is None: status.setText('Ready')
    else: save_entry(result)
   except Exception as e:self.err(f'Could not open connection editor.\n\n{type(e).__name__}: {e}')
  def editone():
   n,v=current()
   if v:save_entry(server_editor('Edit server',v,n),n)
  def cloneone():
   n,v=current()
   if v:save_entry(server_editor('Clone server',v,n+' copy'))
  def removeone():
   n,v=current()
   if not n:return
   if path_is_mounted(mountpoint(n)):return self.err('Disconnect this server before removing it.')
   q=NiruDialog(d); q.setWindowTitle('Remove connection'); ql=QVBoxLayout(q); qt=QLabel(f'<b>Remove “{n}”?</b><br><br>This removes the saved connection from NIRUORG. No files on the server will be changed or deleted.'); qt.setWordWrap(True); ql.addWidget(qt); qb=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok); qb.accepted.connect(q.accept); qb.rejected.connect(q.reject); ql.addWidget(qb)
   if q.exec()==QDialog.DialogCode.Accepted:
    secret_clear(n,v); data.pop(n,None); self._save_json('servers_json',data); refresh(); self.build_sidebar()
  def ssh_args(v,batch=False):
   args=['-p',str(v.get('port',22)),'-o',f'ConnectTimeout={int(v.get("timeout",12))}','-o',f'ServerAliveInterval={int(v.get("keepalive",15))}','-o','ServerAliveCountMax=2']; pj=v.get('proxyjump','').strip(); args += (['-J',pj] if pj else [])
   if batch:args += ['-o','BatchMode=yes']
   if auth(v)=='key':
    key=Path(os.path.expanduser(v.get('key','')))
    if key.exists():args += ['-i',str(key),' -o','IdentitiesOnly=yes'] if False else ['-i',str(key),'-o','IdentitiesOnly=yes']
   return args
  def cleanup_tmp():
   t=state.get('tmp'); state['tmp']=None
   if t:
    try:Path(t).unlink(missing_ok=True)
    except Exception:pass
  def key_auth_failure(detail):
   t=(detail or '').lower()
   return any(x in t for x in ('permission denied','publickey','passphrase','sign_and_send_pubkey','agent refused operation','no identities'))
  def unlock_prompt(n,v,retry):
   q=NiruDialog(d); q.setWindowTitle('Unlock SSH key · '+n); q.resize(570,300); ql=QVBoxLayout(q)
   title=QLabel('SSH key needs to be unlocked'); title.setObjectName('dialogTitle'); ql.addWidget(title)
   body=QLabel('Enter the passphrase for your SSH key. NIRUORG passes it directly to OpenSSH for this unlock attempt; it is not saved in settings, logs, command arguments, environment variables, or files.')
   body.setTextFormat(Qt.TextFormat.PlainText); body.setWordWrap(True); ql.addWidget(body)
   keypath=Path(os.path.expanduser(v.get('key',''))) if auth(v)=='key' and v.get('key') else None
   if keypath:
    kn=QLabel('Key · '+str(keypath)); kn.setObjectName('muted'); kn.setWordWrap(True); ql.addWidget(kn)
   pw=QLineEdit(); pw.setEchoMode(QLineEdit.EchoMode.Password); pw.setPlaceholderText('SSH key passphrase'); pw.setClearButtonEnabled(True); ql.addWidget(pw)
   statusline=QLabel('The key is added only to the active SSH agent session.'); statusline.setObjectName('muted'); statusline.setWordWrap(True); ql.addWidget(statusline); ql.addStretch()
   br=QHBoxLayout(); unlockb=QPushButton('Unlock'); retryb=QPushButton('Retry'); cancelb=QPushButton('Cancel'); br.addStretch(); br.addWidget(unlockb); br.addWidget(retryb); br.addWidget(cancelb); ql.addLayout(br)
   def launch():
    exe=shutil.which('ssh-add')
    if not exe:return self.err('ssh-add is not installed. Install the OpenSSH client tools.')
    if not pw.text():pw.setFocus(); return
    env=self._ssh_agent_environment(True)
    if not env.get('SSH_AUTH_SOCK'):return self.err('NIRUORG could not start or access an SSH authentication agent. Open Connection diagnostics for details, or verify that ssh-agent is installed.')
    secret=pw.text(); pw.clear(); unlockb.setEnabled(False); retryb.setEnabled(False); statusline.setText('Unlocking SSH key…')
    helper_fd_r,helper_fd_w=os.pipe()
    try:
     os.write(helper_fd_w,secret.encode('utf-8')+b'\n')
    finally:
     os.close(helper_fd_w); secret=''
    # mkstemp creates the helper with an unpredictable name and mode 0600.
    # Never write through a predictable filename in shared /tmp.
    helper_fd,helper_name=tempfile.mkstemp(prefix='niruorg-askpass-',suffix='.sh')
    helper=Path(helper_name)
    with os.fdopen(helper_fd,'w',encoding='utf-8') as helper_file:
     helper_file.write('#!/bin/sh\nIFS= read -r pass <&"$NIRUORG_ASKPASS_FD"\nprintf "%s\n" "$pass"\n')
    helper.chmod(0o700)
    args=[exe]+([str(keypath)] if keypath else [])
    pe={**os.environ,**env,'SSH_ASKPASS':str(helper),'SSH_ASKPASS_REQUIRE':'force','DISPLAY':os.environ.get('DISPLAY') or ':0','NIRUORG_ASKPASS_FD':str(helper_fd_r)}
    try:
     r=subprocess.run(args,env=pe,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=20,pass_fds=(helper_fd_r,))
    except Exception as e:
     r=None; detail=str(e)
    finally:
     os.close(helper_fd_r); helper.unlink(missing_ok=True)
    unlockb.setEnabled(True); retryb.setEnabled(True)
    if r and r.returncode==0:
     status.setText('SSH key unlocked · '+n); q.accept(); QTimer.singleShot(100,retry); return
    detail=(r.stderr.strip() if r else detail) or 'OpenSSH rejected the key passphrase.'
    statusline.setText('Could not unlock the SSH key. Check the passphrase and try again.')
    pw.setFocus(); self.err('SSH key unlock failed.\n\n'+detail)
   unlockb.clicked.connect(launch); pw.returnPressed.connect(launch)
   def do_retry():
    q.accept(); QTimer.singleShot(0,retry)
   retryb.clicked.connect(do_retry); cancelb.clicked.connect(q.reject); QTimer.singleShot(0,pw.setFocus); q.exec()
  def finish(ok,detail=''):
   action=state['action']; n=state['name']; mp=state['mount']; retry=state.get('retry'); state['retry']=None; set_busy(False)
   if state['timer']:state['timer'].stop(); state['timer']=None
   state['proc']=None; cleanup_tmp()
   if action=='connect' and ok:QTimer.singleShot(350,lambda: after_mount(n,mp))
   elif action in ('ssh-preflight-connect','ssh-preflight-test'):
    if ok:
     status.setText(f'SSH authentication ready · {n}'); QTimer.singleShot(0,retry) if retry else None
    elif n in data and key_auth_failure(detail):
     status.setText(f'SSH key locked or unavailable · {n}'); QTimer.singleShot(0,lambda: unlock_prompt(n,data[n],retry))
    else:
     status.setText((f'SSH authentication failed · {n}')+(f' · {detail}' if detail else '')); refresh(n)
   else:
    if action=='disconnect' and ok:
     if mp:self._release_mount(mp)
     for pane in (self.pane1,self.pane2):
      if pane.remote_name==n:
       pane.clear_remote(); pane.go(str(Path.home()),leave_remote=True)
    msg=(f'{action.capitalize()} succeeded · {n}' if ok else f'{action.capitalize()} failed · {n}')+(f' · {detail}' if detail else '')
    if not ok and action in ('test','connect') and n in data and protocol(data[n])=='sftp' and auth(data[n]) in ('auto','key') and key_auth_failure(detail):msg += ' · SSH key may need unlocking.'
    status.setText(msg); refresh(n); self.build_sidebar()
  def after_mount(n,mp):
   mounted=bool(mp and path_is_mounted(mp)); set_busy(False); refresh(n); self.build_sidebar()
   cfg=data.get(n)
   if mounted and cfg:
    self._claim_mount(mp,'server',n)
    try:
     # The async mount callback must resolve the connection by name here.
     # Never depend on a stale/free `v` from another nested callback.
     target_pane.bind_remote(n,protocol(cfg),mp,cfg.get('path','/'))
     target_pane.go(mp)
     if not target_pane.is_remote() or not target_pane._path_inside_remote(target_pane.current):
      raise RuntimeError('mounted server was not bound to the target pane')
    except Exception as e:
     target_pane.clear_remote(); status.setText(f'Connected mount could not be opened · {n}'); self.err(f'Remote mount opened but the file pane could not switch to {n}.\n\n{e}'); return
    status.setText(f'Connected · {n}')
    if initial_action=='connect':QTimer.singleShot(100,d.accept)
   elif mounted:
    status.setText(f'Connection definition disappeared before mount completed · {n}')
   else:status.setText(f'Connect command ended but mount is not active · {n}')
  def run_async(program,args,action,n,timeout_s,mount=None,env=None,tmp=None,retry=None):
   if state['proc']:return
   proc=QProcess(d); state.update(proc=proc,action=action,name=n,mount=mount,tmp=tmp,retry=retry); proc.setProgram(program); proc.setArguments(args); proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
   if env:
    pe=proc.processEnvironment()
    for k,v in env.items():pe.insert(k,v)
    proc.setProcessEnvironment(pe)
   set_busy(True,f'{action.capitalize()}… · {n}')
   done={'v':False}
   def ended(code,exitstatus):
    if done['v']:return
    done['v']=True; out=bytes(proc.readAllStandardOutput()).decode(errors='replace').strip(); ok=(code==0 and exitstatus==QProcess.ExitStatus.NormalExit); finish(ok,out[-1000:] if out else '')
   def failed(_):
    if done['v']:return
    done['v']=True; out=bytes(proc.readAllStandardOutput()).decode(errors='replace').strip(); finish(False,out or proc.errorString())
   proc.finished.connect(ended); proc.errorOccurred.connect(failed); timer=QTimer(d); timer.setSingleShot(True); state['timer']=timer
   def timedout():
    if state['proc'] and state['proc'].state()!=QProcess.ProcessState.NotRunning:status.setText(f'{action.capitalize()} timed out · {n}'); state['proc'].kill()
   timer.timeout.connect(timedout); timer.start(max(3,int(timeout_s))*1000); proc.start()
  def obscure(pw):
   exe=shutil.which('rclone')
   if not exe:return None
   try:
    r=subprocess.run([exe,'obscure','-'],input=pw+'\n',text=True,capture_output=True,timeout=4); return r.stdout.strip() if r.returncode==0 else None
   except Exception:return None
  def rclone_config(n,v,pw):
   ob=obscure(pw)
   if not ob:return None
   import tempfile
   fd,path=tempfile.mkstemp(prefix='niruorg-server-',suffix='.conf'); os.close(fd); os.chmod(path,0o600)
   pr=protocol(v); typ='sftp' if pr=='sftp' else 'ftp'; lines=['[remote]',f'type = {typ}',f'host = {v.get("host","")}',f'user = {v.get("user","")}',f'port = {v.get("port",22 if pr=="sftp" else 21)}',f'pass = {ob}']
   if pr in ('ftps','ftps-implicit'):lines += ['tls = true']; lines += [f'explicit_tls = {str(pr=="ftps").lower()}',f'no_check_certificate = {str(not v.get("tls_verify",True)).lower()}']
   Path(path).write_text('\n'.join(lines)+'\n'); return path
  def diagnoseone():
   n,v=current()
   if not v:return
   diagnose.setEnabled(False); status.setText(f'Diagnosing… · {n}')
   worker=ConnectionDiagnosticWorker(n,v); self.running_workers.append(worker)
   def show(rows):
    try:self.running_workers.remove(worker)
    except ValueError:pass
    diagnose.setEnabled(True); status.setText(f'Diagnostics complete · {n}')
    dd=NiruDialog(d); dd.setWindowTitle('Connection diagnostics · '+n); dd.resize(680,480); dl=QVBoxLayout(dd)
    head=QLabel(f'<b>{n}</b><br>{v.get("host","")}:{v.get("port",22)} · read-only diagnostics · no settings were changed'); head.setWordWrap(True); dl.addWidget(head)
    tree=QTreeWidget(); tree.setHeaderLabels(['Stage','Result','Details']); tree.setRootIsDecorated(False); tree.setAlternatingRowColors(True)
    for stage,ok,detail in rows:
     it=QTreeWidgetItem([stage,'OK' if ok else 'FAILED',detail]); tree.addTopLevelItem(it)
    tree.header().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); tree.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents); tree.header().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch); dl.addWidget(tree,1)
    note=QLabel('DNS → Tailscale (when selected) → TCP port → SSH authentication. A TCP failure means authentication and SSH keys have not been reached yet.'); note.setWordWrap(True); note.setObjectName('muted'); dl.addWidget(note)
    cb=QPushButton('Close'); cb.clicked.connect(dd.accept); br=QHBoxLayout(); br.addStretch(); br.addWidget(cb); dl.addLayout(br); dd.exec()
   worker.signals.done.connect(show); self._start_worker(self.threadpool,worker,('done',))
  def testone_raw():
   n,v=current()
   if not v:return
   if protocol(v)=='sftp' and auth(v)!='password':
    exe=shutil.which('ssh')
    if not exe:return self.err('OpenSSH client is not installed.')
    dest=f'{v.get("user")}@{v.get("host")}' if v.get('user') else v.get('host'); return run_async(exe,ssh_args(v,True)+[dest,'true'],'test',n,int(v.get('timeout',12))+3,env=self._ssh_agent_environment(False))
   pw=get_password(n,v)
   if pw is None:return
   exe=shutil.which('rclone')
   if not exe:return self.err('rclone is required for password-based SFTP/FTP/FTPS. Re-run the installer.')
   cfg=rclone_config(n,v,pw)
   if not cfg:return self.err('Could not prepare secure connection configuration.')
   target='remote:'+v.get('path','/'); run_async(exe,['lsd',target,'--config',cfg,'--max-depth','1'],'test',n,int(v.get('timeout',12))+5,tmp=cfg)
  def connectone_raw():
   n,v=current()
   if not v:return
   mp=mountpoint(n); mp.mkdir(parents=True,exist_ok=True)
   if path_is_mounted(mp):status.setText(f'Already connected · {n}'); target_pane.bind_remote(n,protocol(v),mp,v.get('path','/')); target_pane.go(mp); return
   if protocol(v)=='sftp' and auth(v)!='password':
    exe=shutil.which('sshfs')
    if not exe:return self.err('SSHFS is not installed. Re-run the NIRUORG installer or install sshfs.')
    remote=(f'{v.get("user")}@' if v.get('user') else '')+f'{v.get("host")}:{v.get("path","/")}'
    opts=f'reconnect,ConnectTimeout={int(v.get("timeout",12))},ServerAliveInterval={int(v.get("keepalive",15))},ServerAliveCountMax=2'; args=[remote,str(mp),'-p',str(v.get('port',22)),'-o',opts]; pj=v.get('proxyjump','').strip(); args += (['-o',f'ProxyJump={pj}'] if pj else [])
    if auth(v)=='key':
     key=Path(os.path.expanduser(v.get('key','')))
     if key.exists():args += ['-o',f'IdentityFile={key}','-o','IdentitiesOnly=yes']
    return run_async(exe,args,'connect',n,int(v.get('timeout',12))+5,mp,env=self._ssh_agent_environment(False))
   pw=get_password(n,v)
   if pw is None:return
   exe=shutil.which('rclone')
   if not exe:return self.err('rclone is required for password-based SFTP/FTP/FTPS. Re-run the installer.')
   cfg=rclone_config(n,v,pw)
   if not cfg:return self.err('Could not prepare secure connection configuration.')
   target='remote:'+v.get('path','/'); args=['mount',target,str(mp),'--config',cfg,'--vfs-cache-mode','writes','--daemon']
   run_async(exe,args,'connect',n,int(v.get('timeout',12))+8,mp,tmp=cfg)
  def ssh_preflight(n,v,retry,kind):
   exe=shutil.which('ssh')
   if not exe:return self.err('OpenSSH client is not installed.')
   dest=f'{v.get("user")}@{v.get("host")}' if v.get('user') else v.get('host')
   action='ssh-preflight-'+kind
   run_async(exe,ssh_args(v,True)+[dest,'true'],action,n,int(v.get('timeout',12))+3,env=self._ssh_agent_environment(False),retry=retry)
  def testone():
   n,v=current()
   if not v:return
   if protocol(v)=='sftp' and auth(v) in ('auto','key'):
    return ssh_preflight(n,v,testone_raw,'test')
   return testone_raw()
  def connectone():
   n,v=current()
   if not v:return
   mp=mountpoint(n)
   if path_is_mounted(mp):status.setText(f'Already connected · {n}'); target_pane.bind_remote(n,protocol(v),mp,v.get('path','/')); target_pane.go(mp); return
   if protocol(v)=='sftp' and auth(v) in ('auto','key'):
    return ssh_preflight(n,v,connectone_raw,'connect')
   return connectone_raw()
  def disconnectone():
   n,v=current()
   if not n:return
   mp=mountpoint(n)
   if not path_is_mounted(mp):status.setText(f'Not connected · {n}'); return
   exe=shutil.which('fusermount3') or shutil.which('fusermount') or shutil.which('umount')
   if not exe:return self.err('No unmount helper found.')
   args=['-u',str(mp)] if 'fusermount' in Path(exe).name else [str(mp)]; run_async(exe,args,'disconnect',n,8,mp)
  def detailsone():
   n,v=current()
   if not v:return
   mp=mountpoint(n); pr=protocol(v); rt=v.get('route','direct'); route_label={'direct':'Direct / LAN / Internet','tailscale':'Tailscale','tailscale-ssh':'Tailscale SSH'}.get(rt,rt)
   deps=[]
   for label,cmd in [('OpenSSH','ssh'),('SSHFS','sshfs'),('rclone','rclone'),('Tailscale','tailscale'),('Secret Service','secret-tool')]:deps.append(f'{label}: '+('available' if shutil.which(cmd) else 'not installed'))
   text=(f'Connection: {n}\nProtocol: {pr.upper()}\nNetwork: {route_label}\nHost: {v.get("host","")}:{v.get("port",22)}\nUser: {v.get("user","") or "(default)"}\nRemote folder: {v.get("path","/")}\nAuthentication: {auth(v)}\nMounted: {"yes" if path_is_mounted(mp) else "no"}\nLocal mount: {mp}\n\nCapabilities\n'+"\n".join(deps))
   if rt.startswith('tailscale'):text+='\n\nTailscale tip: verify this machine is signed in with `tailscale status`. MagicDNS names and 100.x addresses work as normal SSH/SFTP hosts.'
   dd=NiruDialog(d); dd.setWindowTitle('Connection details · '+n); dd.resize(560,430); dl=QVBoxLayout(dd); title=QLabel(f'<b>{n}</b><br>{pr.upper()} · {route_label}'); title.setWordWrap(True); dl.addWidget(title); grid=QFormLayout(); grid.addRow('Endpoint',QLabel(f'{v.get("host","")}:{v.get("port",22)}')); grid.addRow('Username',QLabel(v.get('user','') or '(OpenSSH default)')); grid.addRow('Start folder',QLabel(v.get('path','/'))); grid.addRow('Authentication',QLabel({'auto':'OpenSSH / Auto','key':'SSH key','password':'Password'}.get(auth(v),auth(v)))); grid.addRow('Status',QLabel('Connected' if path_is_mounted(mp) else 'Disconnected')); grid.addRow('Local mount',QLabel(str(mp))); dl.addLayout(grid); cap=QLabel('<b>Capabilities</b><br>'+ '<br>'.join(deps)); cap.setWordWrap(True); dl.addWidget(cap); dl.addStretch(); close=QPushButton('Close'); close.clicked.connect(dd.accept); br=QHBoxLayout(); br.addStretch(); br.addWidget(close); dl.addLayout(br); dd.exec()
  def unlockkey():
   n,v=current()
   if not v or protocol(v)!='sftp':return
   def done():status.setText('SSH key ready · '+n)
   unlock_prompt(n,v,done)
  def sshopen():
   n,v=current()
   if not v:return
   if protocol(v)!='sftp':return self.err('Interactive SSH is available for SSH/SFTP servers only.')
   exe=shutil.which('ssh')
   if not exe:return self.err('OpenSSH client is not installed.')
   dest=f'{v.get("user")}@{v.get("host")}' if v.get('user') else v.get('host'); cmd=([shutil.which('tailscale'),'ssh',dest] if v.get('route')=='tailscale-ssh' and shutil.which('tailscale') else [exe]+ssh_args(v,False)+[dest])
   if v.get('route')=='tailscale-ssh' and not shutil.which('tailscale'):return self.err('Tailscale CLI is not installed. Install/start Tailscale or change Network to Tailscale · MagicDNS or 100.x IP.')
   # For password auth, the terminal deliberately handles the interactive password prompt; no password is put on the command line.
   if self.terminal and 'kitty' in self.terminal:run_detached([self.terminal,'--hold']+cmd,env=self._ssh_agent_environment(False))
   elif self.terminal:run_detached([self.terminal,'-e']+cmd,env=self._ssh_agent_environment(False))
   else:run_detached(cmd,env=self._ssh_agent_environment(False))
  def cancelone():
   p=state.get('proc')
   if p:status.setText(f'Cancelling · {state["name"]}'); p.terminate(); QTimer.singleShot(1200,lambda: p.kill() if p.state()!=QProcess.ProcessState.NotRunning else None)
  add.clicked.connect(addone); importb.clicked.connect(lambda:(d.accept(),self.import_connections())); edit.clicked.connect(editone); clone.clicked.connect(cloneone); rem.clicked.connect(removeone); test.clicked.connect(testone); diagnose.clicked.connect(diagnoseone); details.clicked.connect(detailsone); unlock.clicked.connect(unlockkey); connect.clicked.connect(connectone); disconnect.clicked.connect(disconnectone); ssh.clicked.connect(sshopen); cancel.clicked.connect(cancelone); w.currentItemChanged.connect(lambda *_:update_actions()); w.itemDoubleClicked.connect(lambda *_:connectone()); refresh(initial_name); update_actions()
  actions={'connect':connectone,'test':testone,'diagnose':diagnoseone,'details':detailsone,'disconnect':disconnectone,'ssh':sshopen,'edit':editone,'clone':cloneone,'remove':removeone}
  if initial_action in actions:QTimer.singleShot(0,actions[initial_action])
  d.exec()
  if state.get('proc') and state['proc'].state()!=QProcess.ProcessState.NotRunning:state['proc'].kill()
  cleanup_tmp()
 def toggle_hidden(self):
  for p in (self.pane1,self.pane2):p.model.setFilter(p.model.filter() ^ QDir.Filter.Hidden)
 def pin_current(self):
  pins=self.s.value('pins',[],type=list) or []; p=str(self.current_dir())
  if p not in pins:pins.append(p); self.s.setValue('pins',pins); self.build_sidebar()
 def actions(self):
  selected=self.selected(); one=selected[0] if len(selected)==1 else None; entries=[]
  def add(label,fn,reason=''):entries.append((label,fn,reason))
  if selected:
   add('Open',self.open_selected,'Selection')
   if one and one.is_file():add('Preview / Inspector',self.preview,'File'); add('Open With…',self.open_with,'File')
   add('Add to Work Basket',self.add_dropzone,'Selection'); add('Copy path',self.copy_path,'Selection'); add('Send to Target…',self.send_target,'Selection')
   if shutil.which('localsend'):add('Send with LocalSend',self.localsend,'LocalSend available')
   if one and one.is_file() and one.suffix.lower() in ('.zip','.tar','.gz','.tgz','.xz','.7z'):add('Browse archive…',self.archive_browser,'Archive')
   if one and one.is_file() and one.suffix.lower() in {'.mp3','.flac','.ogg','.opus','.m4a','.aac','.wav','.wma','.ape'}:add('Play audio',self.play_audio,'Configured audio player')
   elif one and one.is_file() and (mimetypes.guess_type(one.name)[0] or '').startswith('video/') and shutil.which('mpv'):add('Play with MPV',self.mpv,'Video')
   for n,cfg in sorted(self._action_data().items()):
    if self._action_matches(cfg,selected):add('NIRU · '+n,lambda n=n:self._execute_action(n,selected),'Custom action')
  else:
   add('Find files',self.find_files,'Current location'); add('Jump',self.jump,'Navigation'); add('Context Lens',self.context_lens,'Current folder'); add('Open terminal here',self.terminal_here,'Current folder'); add('Work Basket',self.show_dropzone,'Working set'); add('Workspace Snapshots',self.manage_workspaces,'Workspace')
  add('New tab',lambda:self.active.new_tab(),'Pane'); add('Close tab',lambda:self.active.close_tab(self.active.tabs.currentIndex()),'Pane'); add('All actions…',self.all_actions,'Full command list')
  d=NiruDialog(self); d.setWindowTitle('Intent Actions'); d.resize(620,480); l=QVBoxLayout(d); q=QLineEdit(); q.setPlaceholderText('Filter actions…'); w=QTreeWidget(); w.setHeaderLabels(['Action','Why']); w.setRootIsDecorated(False); l.addWidget(q); l.addWidget(w,1); hint=QLabel('Actions are ranked from the current selection and available integrations. Ctrl+K always remains keyboard-first.'); hint.setWordWrap(True); hint.setObjectName('muted'); l.addWidget(hint)
  def fill(text=''):
   w.clear(); needle=text.casefold()
   for i,(label,fn,reason) in enumerate(entries):
    if needle and needle not in (label+' '+reason).casefold():continue
    it=QTreeWidgetItem(w,[label,reason]); it.setData(0,Qt.ItemDataRole.UserRole,i)
   w.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch); w.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
   if w.topLevelItemCount():w.setCurrentItem(w.topLevelItem(0))
  def run():
   it=w.currentItem()
   if not it:return
   fn=entries[it.data(0,Qt.ItemDataRole.UserRole)][1]; d.accept(); fn()
  q.textChanged.connect(fill); q.returnPressed.connect(run); w.itemDoubleClicked.connect(lambda *_:run()); fill(); q.setFocus(); d.exec()
 def all_actions(self):
  """Keyboard-first searchable command palette; execute only after closing the dialog."""
  items=[('New tab',lambda:self.active.new_tab()),('Close tab',lambda:self.active.close_tab(self.active.tabs.currentIndex())),('Open',self.open_selected),('Open With…',self.open_with),('Context Lens',self.context_lens),('New…',self.quick_create),('Find files',self.find_files),('Jump',self.jump),('Focus browser',self.toggle_focus),('Quick Look panel',self.toggle_quicklook),('Preview / Inspector',self.preview),('Open terminal here',self.terminal_here),('Clipboard inspector',self.clipboard_inspector),('Folder health',self.folder_health),('Find duplicates…',self.duplicate_finder),('Saved searches…',self.saved_searches),('NIRU Actions…',self.manage_niru_actions),('Recipes…',self.manage_recipes),('Operation queue',self.operation_queue),('Operation history',self.operation_history),('Work Basket',self.show_dropzone),('Add to Work Basket',self.add_dropzone),('Compare panes',self.compare_panes),('Workspace Snapshots',self.manage_workspaces),('Servers',self.manage_servers),('Import connections…',self.import_connections),('Inspect package…',self.package_inspector),('System diagnostics…',self.system_diagnostics),('Cloud services…',self.manage_clouds),('Integrations…',self.integrations),('Properties',self.properties),('Keybindings',self.show_keybindings)]
  d=NiruDialog(self); d.setWindowTitle('Commands'); d.resize(530,490)
  layout=QVBoxLayout(d); layout.setContentsMargins(16,16,16,16); layout.setSpacing(9)
  query=QLineEdit(d); query.setPlaceholderText('Type a command…'); layout.addWidget(query)
  results=QListWidget(d); layout.addWidget(results,1)
  hint=QLabel('↑ ↓ navigate · Enter run · Esc close',d); hint.setObjectName('muted'); layout.addWidget(hint)
  def refresh(value=''):
   results.clear(); needle=value.casefold().strip()
   for index,(name,_) in enumerate(items):
    if needle and not all(word in name.casefold() for word in needle.split()):continue
    item=QListWidgetItem(name); item.setData(Qt.ItemDataRole.UserRole,index); results.addItem(item)
   if results.count():results.setCurrentRow(0)
  def activate():
   item=results.currentItem()
   if item is None:return
   callback=items[item.data(Qt.ItemDataRole.UserRole)][1]
   d.accept(); QTimer.singleShot(0,callback)
  def move_selection(delta):
   if results.count():results.setCurrentRow((results.currentRow()+delta)%results.count())
  query.textChanged.connect(refresh); query.returnPressed.connect(activate)
  results.itemDoubleClicked.connect(lambda *_:activate())
  QShortcut(QKeySequence('Down'),query,activated=lambda:move_selection(1))
  QShortcut(QKeySequence('Up'),query,activated=lambda:move_selection(-1))
  refresh(); query.setFocus(); d.exec()
 def integration_status(self):
  checks=[('MPV','mpv'),('LocalSend','localsend'),('fd','fd'),('ripgrep','rg'),('7-Zip','7z'),('SSH','ssh'),('SSHFS','sshfs'),('Secret Service','secret-tool'),('Proton Pass CLI · optional','pass-cli'),('ffprobe','ffprobe'),('rclone','rclone'),('NIRUNOTE','nirunote'),('NIRUPRES','nirupres'),('NIRUWORD','niruword')]
  return [(label, shutil.which(cmd) or ('fdfind' if cmd=='fd' and shutil.which('fdfind') else None)) for label,cmd in checks]
 def _rclone_remotes(self):
  exe=shutil.which('rclone')
  if not exe:return []
  try:
   r=subprocess.run([exe,'listremotes'],capture_output=True,text=True,timeout=8)
   if r.returncode:return []
   return [x.strip().rstrip(':') for x in r.stdout.splitlines() if x.strip()]
  except Exception:return []
 def _rclone_remote_type(self,name):
  exe=shutil.which('rclone')
  if not exe:return ''
  # redacted never exposes OAuth tokens; older rclone versions simply fall back to a generic label.
  try:
   r=subprocess.run([exe,'config','redacted',name],capture_output=True,text=True,timeout=5)
   if r.returncode:return ''
   for line in r.stdout.splitlines():
    if line.strip().startswith('type ='):return line.split('=',1)[1].strip()
  except Exception:pass
  return ''
 def _cloud_label(self,name):
  typ=self._rclone_remote_type(name)
  names={'drive':'Google Drive','onedrive':'OneDrive / Microsoft 365','dropbox':'Dropbox','s3':'S3','webdav':'WebDAV','box':'Box'}
  return f'{names.get(typ,"Cloud")} · {name}'
 def _cloud_mountpoint(self,name):
  safe=''.join(c if c.isalnum() or c in '-_.' else '_' for c in name)
  return Path.home()/'.local/share/niruorg/cloud'/safe
 def _cloud_sidebar_entries(self):
  out=[]; nc=Path.home()/'Nextcloud'; out.append(('Nextcloud',str(nc),f'Local Nextcloud sync · {nc}','cloud:nextcloud'))
  mounts=mounted_paths()
  for name in self._cloud_cache:
   mp=self._cloud_mountpoint(name); mounted=path_is_mounted(mp,mounts); typ=self._cloud_types.get(name,'')
   names={'drive':'Google Drive','onedrive':'OneDrive / Microsoft 365','dropbox':'Dropbox','s3':'S3','webdav':'WebDAV','box':'Box'}; label=f'{names.get(typ,"Cloud")} · {name}'
   out.append((('●  ' if mounted else '○  ')+label,str(mp) if mounted else '__cloud__:'+name,('Mounted · checked lazily' if mounted else 'Click to mount · ')+name,'cloud:'+name))
  out.append(('+  Add / manage cloud…','__cloud_manager__','Google Drive, OneDrive / Microsoft 365, Dropbox, WebDAV and other rclone providers','cloud-manager'))
  return out
 def _terminal_command(self,args):
  cmd=' '.join(shlex.quote(str(x)) for x in args)
  if self.terminal:
   base=Path(self.terminal).name
   if base=='kitty':return run_detached([self.terminal,'--hold',self.shell,'-lc',cmd])
   return run_detached([self.terminal,'-e',self.shell,'-lc',cmd])
  return False
 def open_cloud(self,name,target_pane=None):
  target_pane=target_pane or self.active
  exe=shutil.which('rclone')
  if not exe:return self.err('rclone is not installed. Open Cloud services for installation information.')
  if name not in self._rclone_remotes():return self.err(f'Cloud remote not found: {name}')
  mp=self._cloud_mountpoint(name); mp.mkdir(parents=True,exist_ok=True)
  created_here=not path_is_mounted(mp)
  if created_here:
   r=subprocess.run([exe,'mount',name+':',str(mp),'--vfs-cache-mode','writes','--daemon'],capture_output=True,text=True,timeout=20)
   if r.returncode:return self.err(r.stderr.strip() or f'Could not mount {name}. Ensure FUSE is installed and the cloud login is valid.')
   for _ in range(20):
    QApplication.processEvents()
    if path_is_mounted(mp):break
    import time; time.sleep(.1)
  if not path_is_mounted(mp):return self.err(f'{name} did not become available at {mp}.')
  if created_here:self._claim_mount(mp,'cloud',name)
  self.build_sidebar(); target_pane.bind_remote(name,'CLOUD',mp,'/'); target_pane.go(str(mp)); self.set_active(target_pane); self.status.setText(f'Cloud mounted · {name}')
 def unmount_cloud(self,name):
  mp=self._cloud_mountpoint(name)
  if not path_is_mounted(mp):return
  cmd=shutil.which('fusermount3') or shutil.which('fusermount') or shutil.which('umount')
  if not cmd:return self.err('No FUSE unmount command is available.')
  args=[cmd,'-u',str(mp)] if 'fusermount' in Path(cmd).name else [cmd,str(mp)]
  r=subprocess.run(args,capture_output=True,text=True)
  if r.returncode:return self.err(r.stderr.strip() or f'Could not unmount {name}.')
  self._release_mount(mp)
  for pane in (self.pane1,self.pane2):
   if pane.remote_name==name and pane.remote_protocol=='CLOUD':pane.clear_remote(); pane.go(str(Path.home()),leave_remote=True)
  self.build_sidebar(); self.status.setText(f'Cloud unmounted · {name}')
 def manage_clouds(self):
  d=NiruDialog(self); d.setWindowTitle('Cloud services'); d.resize(700,500); l=QVBoxLayout(d)
  l.addWidget(QLabel('<b>Cloud services</b><br>NIRUORG uses rclone for remote cloud access. OAuth credentials remain in rclone; NIRUORG does not store your Google or Microsoft password.'))
  w=QTreeWidget(); w.setHeaderLabels(['Service / remote','Status','Mount point']); w.setRootIsDecorated(False); l.addWidget(w,1)
  def refresh():
   w.clear()
   nc=Path.home()/'Nextcloud'
   if nc.exists():QTreeWidgetItem(w,['Nextcloud','Local sync',str(nc)])
   for name in self._rclone_remotes():
    mp=self._cloud_mountpoint(name); it=QTreeWidgetItem(w,[self._cloud_label(name),'Mounted' if path_is_mounted(mp) else 'Ready',str(mp)]); it.setData(0,Qt.ItemDataRole.UserRole,name)
   self.build_sidebar()
  def require_rclone():
   if shutil.which('rclone'):return True
   self.err('rclone is required for Google Drive, OneDrive / Microsoft 365 and other remote clouds.\n\nInstall package: rclone\nThen reopen Cloud services.')
   return False
  def add_provider(provider):
   if not require_rclone():return
   hints={'Google Drive':'In rclone choose Google Drive (drive) and complete the browser OAuth login.','OneDrive / Microsoft 365':'In rclone choose Microsoft OneDrive (onedrive). The same provider supports personal OneDrive and Microsoft 365 work/school accounts.','Other':'Choose any rclone provider you need, such as Dropbox, WebDAV, S3 or Box.'}
   self.info('Connect '+provider,hints[provider]+'\n\nNIRUORG will now open rclone configuration in a terminal. Return here and press Refresh when authentication is complete.')
   if not self._terminal_command([shutil.which('rclone'),'config']):self.err('Could not open a terminal for rclone configuration.')
  row=QHBoxLayout(); addg=QPushButton('Add Google Drive…'); addm=QPushButton('Add OneDrive / M365…'); addo=QPushButton('Other provider…'); mount=QPushButton('Mount / Open'); unmount=QPushButton('Unmount'); ref=QPushButton('Refresh')
  for b in (addg,addm,addo):row.addWidget(b)
  row.addStretch(); row.addWidget(mount); row.addWidget(unmount); row.addWidget(ref); l.addLayout(row)
  def current():
   it=w.currentItem(); return it.data(0,Qt.ItemDataRole.UserRole) if it else None
  addg.clicked.connect(lambda:add_provider('Google Drive')); addm.clicked.connect(lambda:add_provider('OneDrive / Microsoft 365')); addo.clicked.connect(lambda:add_provider('Other')); ref.clicked.connect(refresh); mount.clicked.connect(lambda:self.open_cloud(current()) if current() else None); unmount.clicked.connect(lambda:self.unmount_cloud(current()) if current() else None); w.itemDoubleClicked.connect(lambda *_:self.open_cloud(current()) if current() else None)
  b=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); b.rejected.connect(d.reject); l.addWidget(b); refresh(); d.exec(); self.build_sidebar()
 def integrations(self):
  d=NiruDialog(self); d.setWindowTitle('Integrations'); d.resize(680,520); l=QVBoxLayout(d); l.addWidget(QLabel('<b>Optional integrations</b><br>Detected on demand; none run as NIRUORG background services.'))
  table=QTreeWidget(); table.setHeaderLabels(['Integration','Status','Executable']); table.setRootIsDecorated(False)
  for label,path in self.integration_status():
   QTreeWidgetItem(table,[label,'Available' if path else 'Not installed',str(path or '—')])
  table.header().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); table.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents); table.header().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch); l.addWidget(table,1)
  proton=QGroupBox('Proton Pass · optional'); pf=QFormLayout(proton); pcli=shutil.which('pass-cli'); pf.addRow('CLI',QLabel(str(pcli or 'Not installed'))); pf.addRow('Mode',QLabel('Optional credential/SSH provider · NIRUORG never requires Proton Pass')); l.addWidget(proton)
  cloud=Path.home()/'Nextcloud'; nc=QGroupBox('Nextcloud sharing'); f=QFormLayout(nc); url=QLineEdit(self.s.value('nextcloud_url','')); user=QLineEdit(self.s.value('nextcloud_user','')); f.addRow('Server URL',url); f.addRow('Username',user); secret=QPushButton('Store / replace app password…'); test=QPushButton('Test API'); row=QHBoxLayout(); row.addWidget(secret); row.addWidget(test); f.addRow(row); f.addRow(QLabel(f'Local sync folder: {cloud if cloud.exists() else "not detected"}')); l.addWidget(nc)
  def store():
   if not shutil.which('secret-tool'):return self.err('secret-tool is not installed. Re-run the installer to add secure credential storage.')
   pw,ok=QInputDialog.getText(d,'Nextcloud app password','App password:',QLineEdit.EchoMode.Password)
   if ok and pw:
    r=subprocess.run(['secret-tool','store','--label=NIRUORG Nextcloud','application','niruorg','service','nextcloud','user',user.text().strip()],input=pw,text=True,capture_output=True)
    if r.returncode:self.err(r.stderr or 'Could not store credential.')
    else:self.info('Nextcloud','App password stored in the system Secret Service.')
  def save():self.s.setValue('nextcloud_url',url.text().strip().rstrip('/')); self.s.setValue('nextcloud_user',user.text().strip())
  def testapi():
   save()
   try:self._nextcloud_request('/ocs/v2.php/cloud/capabilities'); self.info('Nextcloud','API connection successful.')
   except Exception as e:self.err(e)
  secret.clicked.connect(store); test.clicked.connect(testapi); b=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); b.rejected.connect(d.reject); b.clicked.connect(lambda *_:save()); l.addWidget(b); d.exec(); save()
 def _nextcloud_secret(self):
  user=self.s.value('nextcloud_user','')
  if not user or not shutil.which('secret-tool'):return ''
  r=subprocess.run(['secret-tool','lookup','application','niruorg','service','nextcloud','user',user],text=True,capture_output=True)
  return r.stdout.strip() if r.returncode==0 else ''
 def _nextcloud_request(self,path,data=None):
  url=self.s.value('nextcloud_url','').rstrip('/'); user=self.s.value('nextcloud_user',''); pw=self._nextcloud_secret()
  if not url or not user:return (_ for _ in ()).throw(RuntimeError('Configure Nextcloud server and username in Settings → Integrations.'))
  if not pw:return (_ for _ in ()).throw(RuntimeError('No Nextcloud app password is available in the system Secret Service.'))
  body=urllib.parse.urlencode(data).encode() if data else None; req=urllib.request.Request(url+path,data=body); req.add_header('Authorization','Basic '+base64.b64encode(f'{user}:{pw}'.encode()).decode()); req.add_header('OCS-APIRequest','true'); req.add_header('Accept','application/json')
  with urllib.request.urlopen(req,timeout=8) as r:return json.loads(r.read().decode())
 def _inside_nextcloud(self):
  try:return self.current_dir().resolve().is_relative_to((Path.home()/'Nextcloud').resolve())
  except:return False
 def nextcloud_share(self):
  s=self.selected()
  if len(s)!=1:return self.err('Select exactly one Nextcloud file or folder.')
  root=Path.home()/'Nextcloud'; p=s[0]
  try:rel='/' + str(p.resolve().relative_to(root.resolve()))
  except:return self.err('The selected item is not inside ~/Nextcloud.')
  try:
   res=self._nextcloud_request('/ocs/v2.php/apps/files_sharing/api/v1/shares',{'path':rel,'shareType':'3','permissions':'1','format':'json'}); data=res.get('ocs',{}).get('data',{}); url=data.get('url') if isinstance(data,dict) else None
   if not url:raise RuntimeError(res.get('ocs',{}).get('meta',{}).get('message','Nextcloud did not return a public URL.'))
   QApplication.clipboard().setText(url); self.info('Nextcloud public link',url+'\n\nCopied to clipboard.')
  except Exception as e:self.err(e)
 def media_info(self,p):
  exe=shutil.which('ffprobe')
  if not exe:return ''
  try:
   r=subprocess.run([exe,'-v','quiet','-print_format','json','-show_format','-show_streams',str(p)],text=True,capture_output=True,timeout=4)
   j=json.loads(r.stdout or '{}'); fmt=j.get('format',{}); dur=float(fmt.get('duration',0) or 0); lines=[]
   if dur:lines.append(f'Duration: {int(dur//60):02d}:{int(dur%60):02d}')
   for st in j.get('streams',[])[:4]:
    typ=st.get('codec_type'); codec=st.get('codec_name','?')
    if typ=='video':lines.append(f'Video: {codec} · {st.get("width","?")}×{st.get("height","?")}')
    elif typ=='audio':lines.append(f'Audio: {codec} · {st.get("sample_rate","?")} Hz · {st.get("channels","?")} ch')
   tags=fmt.get('tags',{}); 
   for k in ('artist','album','title'): 
    if tags.get(k):lines.append(f'{k.title()}: {tags[k]}')
   return '\n'.join(lines)
  except:return ''
 def clipboard_inspector(self):
  d=NiruDialog(self); d.setWindowTitle('Clipboard'); d.resize(680,430); l=QVBoxLayout(d); w=QListWidget()
  existing=[Path(x) for x in self.clip if Path(x).exists()]
  for p in existing:w.addItem(str(p))
  mode='Cut' if self.cut_mode else 'Copy'
  l.addWidget(QLabel(f'<b>{mode} clipboard</b> · {len(existing)} item(s)')); l.addWidget(w,1)
  row=QHBoxLayout(); paste=QPushButton('Paste here'); clear=QPushButton('Clear'); row.addWidget(clear); row.addStretch(); row.addWidget(paste); l.addLayout(row)
  paste.setEnabled(bool(existing)); paste.clicked.connect(lambda:(self.paste(),d.accept())); clear.clicked.connect(lambda:(self.clip.clear(),setattr(self,'cut_mode',False),d.accept(),self.update_status())); d.exec()
 def folder_health(self):
  base=self.current_dir(); issues=[]; counts={'files':0,'folders':0,'symlinks':0,'empty':0,'broken':0,'unreadable':0,'large':0}
  try:
   for p in base.iterdir():
    try:
     if p.is_symlink():
      counts['symlinks']+=1
      if not p.exists():counts['broken']+=1; issues.append(('Broken symlink',p.name))
     elif p.is_dir():
      counts['folders']+=1
      try:
       if not any(p.iterdir()):counts['empty']+=1; issues.append(('Empty folder',p.name))
      except PermissionError:counts['unreadable']+=1; issues.append(('Unreadable folder',p.name))
     else:
      counts['files']+=1
      if not os.access(p,os.R_OK):counts['unreadable']+=1; issues.append(('Unreadable file',p.name))
      try:
       if p.stat().st_size>=1024**3:counts['large']+=1; issues.append(('Large file ≥ 1 GiB',p.name))
      except OSError:pass
    except OSError as e:issues.append(('Error',f'{p.name}: {e}'))
  except Exception as e:return self.err(e)
  d=NiruDialog(self); d.setWindowTitle('Folder health'); d.resize(760,520); l=QVBoxLayout(d); l.addWidget(QLabel(f'<b>{base}</b><br>{counts["folders"]} folders · {counts["files"]} files · {counts["symlinks"]} symlinks'))
  w=QTreeWidget(); w.setHeaderLabels(['Finding','Item']); w.setRootIsDecorated(False)
  if issues:
   for kind,name in issues:QTreeWidgetItem(w,[kind,name])
  else:QTreeWidgetItem(w,['No obvious issues found','Direct children checked'])
  w.header().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); w.header().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch); l.addWidget(w,1); l.addWidget(QLabel('Fast, non-recursive diagnostic. Nothing is changed or deleted.')); d.exec()
 def duplicate_finder(self):
  base=self.current_dir(); dlg=QProgressDialog('Scanning for duplicate files…','Cancel',0,0,self); dlg.setWindowTitle('Find duplicates'); dlg.setMinimumDuration(0); dlg.show(); by_size={}; scanned=0
  try:
   for root,dirs,files in os.walk(base):
    dirs[:]=[x for x in dirs if x not in ('.git','.cache','node_modules')]
    for name in files:
     QApplication.processEvents()
     if dlg.wasCanceled():dlg.close(); return
     p=Path(root)/name
     try:size=p.stat().st_size
     except OSError:continue
     if size:by_size.setdefault(size,[]).append(p)
     scanned+=1
     if scanned>=50000:break
    if scanned>=50000:break
   import hashlib
   groups=[]
   for size,paths in by_size.items():
    if len(paths)<2:continue
    hashes={}
    for p in paths:
     QApplication.processEvents()
     if dlg.wasCanceled():dlg.close(); return
     try:
      h=hashlib.sha256()
      with p.open('rb') as f:
       while True:
        b=f.read(4*1024*1024)
        if not b:break
        h.update(b)
      hashes.setdefault(h.hexdigest(),[]).append(p)
     except OSError:pass
    groups.extend((size,x) for x in hashes.values() if len(x)>1)
  finally:dlg.close()
  d=NiruDialog(self); d.setWindowTitle('Duplicates'); d.resize(900,600); l=QVBoxLayout(d); tree=QTreeWidget(); tree.setHeaderLabels(['File','Size','Group']); tree.setRootIsDecorated(False)
  for gi,(size,paths) in enumerate(groups,1):
   for p in paths:QTreeWidgetItem(tree,[str(p),human(size),str(gi)])
  tree.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch); tree.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents); tree.header().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents); l.addWidget(QLabel(f'{sum(len(x) for _,x in groups)} duplicate file(s) in {len(groups)} verified SHA-256 group(s) · scanned {scanned} files')); l.addWidget(tree,1); l.addWidget(QLabel('Read-only result. NIRUORG never deletes duplicate candidates automatically.')); d.exec()
 def saved_searches(self):
  data=self._json_setting('saved_searches_json'); d=NiruDialog(self); d.setWindowTitle('Saved searches'); d.resize(700,470); l=QVBoxLayout(d); w=QListWidget()
  def refresh():
   w.clear()
   for n,v in sorted(data.items()):w.addItem(f'{n}   ·   {v.get("term","")}   ·   {v.get("scope","Current folder")}')
  refresh(); l.addWidget(QLabel('Saved searches store the query, not an index. They run on demand.')); l.addWidget(w,1); row=QHBoxLayout(); rem=QPushButton('Remove'); run=QPushButton('Run'); row.addWidget(rem); row.addStretch(); row.addWidget(run); l.addLayout(row)
  def chosen():
   it=w.currentItem()
   if not it:return None
   name=it.text().split('   ·   ',1)[0]; return name
  def dorun():
   n=chosen()
   if n:d.accept(); self.find_files(data[n])
  def remove():
   n=chosen()
   if n:data.pop(n,None); self._save_json('saved_searches_json',data); refresh()
  run.clicked.connect(dorun); rem.clicked.connect(remove); w.itemDoubleClicked.connect(lambda *_:dorun()); d.exec()
 def _action_data(self):
  return self._json_setting('niru_actions_json')
 def _recipe_data(self):
  return self._json_setting('recipes_json')
 def _action_matches(self,cfg,items):
  kind=cfg.get('applies','Any')
  if kind=='Any':return True
  if kind=='Files':return bool(items) and all(p.is_file() for p in items)
  if kind=='Folders':return bool(items) and all(p.is_dir() for p in items)
  if kind=='Images':return bool(items) and all((mimetypes.guess_type(p.name)[0] or '').startswith('image/') for p in items)
  return True
 def _expand_action(self,cfg,items):
  # Commands are parsed into argv first; no shell=True. Placeholders are
  # expanded as individual arguments, preventing filenames from becoming code.
  argv=shlex.split(cfg.get('command',''))
  if not argv:raise RuntimeError('Action has no command.')
  out=[]
  for token in argv:
   if token=='{files}':out.extend(str(p) for p in items); continue
   p=items[0] if items else self.current_dir()
   out.append(token.replace('{file}',str(p)).replace('{name}',p.name).replace('{stem}',p.stem).replace('{dir}',str(p if p.is_dir() else p.parent)))
  return out
 def _execute_action(self,name,items=None,quiet=False):
  items=list(items if items is not None else self.selected()); data=self._action_data(); cfg=data.get(name)
  if not cfg:return self.err(f'Unknown action: {name}')
  if not self._action_matches(cfg,items):return self.err(f'Action “{name}” does not apply to this selection.')
  try:
   argv=self._expand_action(cfg,items); exe=shutil.which(argv[0]) or (argv[0] if Path(argv[0]).exists() else None)
   if not exe:raise RuntimeError(f'Executable not found: {argv[0]}')
   argv[0]=exe; cwd=str(self.current_dir()); subprocess.Popen(argv,cwd=cwd,start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   self.status.setText(f'Action started · {name}')
   return True
  except Exception as e:
   if not quiet:self.err(e)
   return False
 def run_niru_action(self,items=None):
  items=list(items if items is not None else self.selected()); data=self._action_data(); names=[n for n,c in sorted(data.items()) if self._action_matches(c,items)]
  if not names:return self.err('No NIRU Actions match this selection. Create one in Actions → NIRU Actions…')
  name,ok=QInputDialog.getItem(self,'NIRU Actions','Action:',names,0,False)
  if ok:self._execute_action(name,items)
 def manage_niru_actions(self):
  data=self._action_data(); d=NiruDialog(self); d.setWindowTitle('NIRU Actions'); d.resize(820,520); l=QVBoxLayout(d); w=QTreeWidget(); w.setHeaderLabels(['Name','Applies to','Command']); w.setRootIsDecorated(False)
  def refresh():
   w.clear()
   for n,c in sorted(data.items()):QTreeWidgetItem(w,[n,c.get('applies','Any'),c.get('command','')])
   w.header().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); w.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents); w.header().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
  def edit(existing=None):
   cfg=data.get(existing,{}) if existing else {}; x=NiruDialog(d); x.setWindowTitle('Edit NIRU Action' if existing else 'New NIRU Action'); f=QFormLayout(x); name=QLineEdit(existing or ''); applies=QComboBox(); applies.addItems(['Any','Files','Folders','Images']); applies.setCurrentText(cfg.get('applies','Any')); cmd=QLineEdit(cfg.get('command','')); cmd.setPlaceholderText('program --option {files}'); f.addRow('Name',name); f.addRow('Applies to',applies); f.addRow('Command',cmd); hint=QLabel('Placeholders: {files}, {file}, {name}, {stem}, {dir}. Commands run as argv without a shell.'); hint.setWordWrap(True); hint.setObjectName('muted'); f.addRow(hint); b=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); [z.setIcon(QIcon()) for z in b.buttons()]; b.accepted.connect(x.accept); b.rejected.connect(x.reject); f.addRow(b)
   if x.exec()!=QDialog.DialogCode.Accepted:return
   n=name.text().strip(); c=cmd.text().strip()
   if not n or not c:return
   if existing and existing!=n:data.pop(existing,None)
   data[n]={'applies':applies.currentText(),'command':c}; self._save_json('niru_actions_json',data); refresh()
  row=QHBoxLayout(); add=QPushButton('New…'); ed=QPushButton('Edit…'); rem=QPushButton('Remove'); close=QPushButton('Close'); row.addWidget(add); row.addWidget(ed); row.addWidget(rem); row.addStretch(); row.addWidget(close); l.addWidget(QLabel('Reusable, selection-aware commands. Nothing runs in the background.')); l.addWidget(w,1); l.addLayout(row); refresh()
  def chosen():return w.currentItem().text(0) if w.currentItem() else None
  add.clicked.connect(lambda:edit()); ed.clicked.connect(lambda:edit(chosen()) if chosen() else None); rem.clicked.connect(lambda:(data.pop(chosen(),None),self._save_json('niru_actions_json',data),refresh()) if chosen() else None); close.clicked.connect(d.accept); w.itemDoubleClicked.connect(lambda *_:edit(chosen())); d.exec()
 def run_recipe(self,items=None):
  items=list(items if items is not None else self.selected()); recipes=self._recipe_data()
  if not recipes:return self.err('No Recipes yet. Create one in Actions → Recipes…')
  name,ok=QInputDialog.getItem(self,'Recipes','Recipe:',sorted(recipes),0,False)
  if not ok:return
  steps=recipes.get(name,[]); actions=self._action_data(); missing=[x for x in steps if x not in actions]
  if missing:return self.err('Recipe references missing action(s): '+', '.join(missing))
  if not self.confirm('Run Recipe',f'Run “{name}” on {len(items)} selected item(s)?\n\n'+ '\n'.join(f'{i+1}. {x}' for i,x in enumerate(steps)),'Run'):return
  for step in steps:
   if not self._execute_action(step,items):break
 def manage_recipes(self):
  actions=self._action_data(); data=self._recipe_data()
  if not actions:return self.err('Create at least one NIRU Action first.')
  d=NiruDialog(self); d.setWindowTitle('Recipes'); d.resize(760,500); l=QVBoxLayout(d); w=QTreeWidget(); w.setHeaderLabels(['Recipe','Steps']); w.setRootIsDecorated(False)
  def refresh():
   w.clear()
   for n,steps in sorted(data.items()):QTreeWidgetItem(w,[n,' → '.join(steps)])
   w.header().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); w.header().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
  def edit(existing=None):
   name,ok=QInputDialog.getText(d,'Recipe','Name:',text=existing or '')
   if not ok or not name.strip():return
   current=data.get(existing,[]) if existing else []; choices=list(sorted(actions)); selected=[]
   while True:
    a,ok=QInputDialog.getItem(d,'Recipe steps','Add action (Cancel when finished):',choices,0,False)
    if not ok:break
    selected.append(a)
   if not selected and current:selected=current
   if not selected:return
   if existing and existing!=name.strip():data.pop(existing,None)
   data[name.strip()]=selected; self._save_json('recipes_json',data); refresh()
  row=QHBoxLayout(); add=QPushButton('New…'); ed=QPushButton('Edit…'); rem=QPushButton('Remove'); close=QPushButton('Close'); row.addWidget(add); row.addWidget(ed); row.addWidget(rem); row.addStretch(); row.addWidget(close); l.addWidget(QLabel('Recipes chain existing NIRU Actions. A confirmation preview is always shown before execution.')); l.addWidget(w,1); l.addLayout(row); refresh()
  def chosen():return w.currentItem().text(0) if w.currentItem() else None
  add.clicked.connect(lambda:edit()); ed.clicked.connect(lambda:edit(chosen()) if chosen() else None); rem.clicked.connect(lambda:(data.pop(chosen(),None),self._save_json('recipes_json',data),refresh()) if chosen() else None); close.clicked.connect(d.accept); d.exec()
 def find_files(self,preset=None):
  d=NiruDialog(self); d.setWindowTitle('Search Workspace'); d.resize(980,680); outer=QVBoxLayout(d); top=QGridLayout(); q=QLineEdit(); q.setPlaceholderText('File name, wildcard or text…'); scope=QComboBox(); scope.addItems(['Current folder','Home']); content=QCheckBox('Search file contents'); hidden=QCheckBox('Include hidden'); preset=preset or {}; q.setText(preset.get('term','')); scope.setCurrentText(preset.get('scope','Current folder')); content.setChecked(bool(preset.get('content',False))); hidden.setChecked(bool(preset.get('hidden',False))); top.addWidget(QLabel('Search'),0,0); top.addWidget(q,0,1,1,3); top.addWidget(QLabel('Scope'),1,0); top.addWidget(scope,1,1); top.addWidget(content,1,2); top.addWidget(hidden,1,3); outer.addLayout(top)
  results=QTreeWidget(); results.setHeaderLabels(['Name','Folder','Type']); results.setRootIsDecorated(False); results.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); outer.addWidget(results,1); status=QLabel('Ready · searches run in the background'); status.setObjectName('muted'); outer.addWidget(status)
  row=QHBoxLayout(); go=QPushButton('Search'); cancel=QPushButton('Cancel'); cancel.setEnabled(False); saveq=QPushButton('Save search'); addbasket=QPushButton('Add to Work Basket'); openb=QPushButton('Open'); folderb=QPushButton('Open containing folder'); row.addWidget(go); row.addWidget(cancel); row.addWidget(saveq); row.addWidget(addbasket); row.addStretch(); row.addWidget(folderb); row.addWidget(openb); outer.addLayout(row)
  state={'worker':None,'generation':0,'count':0}
  def add_result(raw):
   p=Path(raw)
   try:typ='Folder' if p.is_dir() else (mimetypes.guess_type(p.name)[0] or 'File')
   except:typ='File'
   it=QTreeWidgetItem(results,[p.name,str(p.parent),typ]); it.setData(0,Qt.ItemDataRole.UserRole,str(p)); results.addTopLevelItem(it)
  def runsearch():
   term=q.text().strip()
   if not term:return
   if state['worker']:state['worker'].cancel()
   state['generation']+=1; gen=state['generation']; state['count']=0; results.clear(); base=self.current_dir() if scope.currentIndex()==0 else Path.home(); worker=SearchWorker(base,term,content.isChecked(),hidden.isChecked(),gen); state['worker']=worker; go.setEnabled(False); cancel.setEnabled(True); status.setText(f'Searching · {base}')
   def progress(done,total,raw):
    if gen!=state['generation']:return
    state['count']=done; add_result(raw); status.setText(f'Searching… {done} result(s) · Cancel is available')
   def done(payload):
    if payload.get('generation')!=state['generation']:return
    state['worker']=None; go.setEnabled(True); cancel.setEnabled(False); status.setText(('Cancelled · ' if payload.get('cancelled') else '')+f'{state["count"]} result(s)')
   def failed(msg):
    if gen!=state['generation']:return
    state['worker']=None; go.setEnabled(True); cancel.setEnabled(False); status.setText('Search failed'); self.err(msg)
   worker.signals.progress.connect(progress); worker.signals.done.connect(done); worker.signals.failed.connect(failed); self._start_worker(self.threadpool,worker)
  def cancelsearch():
   if state['worker']:state['worker'].cancel(); status.setText('Cancelling…')
  def selected_paths():return [Path(it.data(0,Qt.ItemDataRole.UserRole)) for it in results.selectedItems()]
  def selected_path():
   it=results.currentItem(); return Path(it.data(0,Qt.ItemDataRole.UserRole)) if it else None
  def openone():
   p=selected_path()
   if p:self.active.go(p) if p.is_dir() else QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
  def containing():
   p=selected_path()
   if p:self.active.go(p.parent); d.accept()
  def basket():
   paths=selected_paths()
   if not paths:return
   self.add_dropzone(paths)
  def savesearch():
   term=q.text().strip()
   if not term:return
   name,ok=QInputDialog.getText(d,'Save search','Name:',text=term)
   if ok and name.strip():
    data=self._json_setting('saved_searches_json'); data[name.strip()]={'term':term,'scope':scope.currentText(),'content':content.isChecked(),'hidden':hidden.isChecked()}; self._save_json('saved_searches_json',data); status.setText(f'Saved search · {name.strip()}')
  saveq.clicked.connect(savesearch); go.clicked.connect(runsearch); cancel.clicked.connect(cancelsearch); addbasket.clicked.connect(basket); q.returnPressed.connect(runsearch); openb.clicked.connect(openone); folderb.clicked.connect(containing); results.itemDoubleClicked.connect(lambda *_:openone()); d.finished.connect(lambda *_: state['worker'].cancel() if state['worker'] else None); q.setFocus(); d.exec()
 def info(self,title,text):
  box=QMessageBox(self); box.setWindowTitle(title); box.setIcon(QMessageBox.Icon.NoIcon); box.setText(str(text)); box.addButton(QMessageBox.StandardButton.Ok); box.exec()
 def confirm(self,title,text,accept='Continue'):
  box=NiruDialog(self); box.setWindowTitle(title); lay=QVBoxLayout(box); lab=QLabel(str(text)); lab.setWordWrap(True); lay.addWidget(lab); row=QHBoxLayout(); row.addStretch(); cancel=QPushButton('Cancel'); ok=QPushButton(accept); ok.setDefault(True); ok.setAutoDefault(True); cancel.setAutoDefault(False); cancel.clicked.connect(box.reject); ok.clicked.connect(box.accept); row.addWidget(cancel); row.addWidget(ok); lay.addLayout(row); QTimer.singleShot(0,ok.setFocus); return box.exec()==QDialog.DialogCode.Accepted
 def err(self,e):
  box=QMessageBox(self); box.setWindowTitle(APP); box.setIcon(QMessageBox.Icon.NoIcon); box.setText(str(e)); box.addButton(QMessageBox.StandardButton.Ok); box.exec()
def main():
 if '--version' in sys.argv:print(VERSION);return 0
 if '--self-test' in sys.argv:
  assert human(1024)=='1.0 KB'; assert 'Nord' in THEMES; assert VERSION=='0.4.0'; assert ConnectionDiagnosticWorker; assert hasattr(Main,'undo_last'); assert hasattr(FilePane,'update_breadcrumbs'); assert hasattr(Main,'manage_servers'); assert hasattr(Main,'open_server_named'); assert hasattr(Main,'manage_workspaces'); assert hasattr(Main,'manage_targets'); assert hasattr(Main,'smart_view'); assert hasattr(Main,'operation_history'); assert hasattr(Main,'format_dt'); assert hasattr(Main,'integrations'); assert hasattr(Main,'nextcloud_share'); assert hasattr(Main,'media_info'); assert hasattr(Main,'niru_player'); assert hasattr(Main,'play_audio'); assert hasattr(Main,'storage_view'); assert hasattr(Main,'permissions_view'); assert hasattr(Main,'operation_queue'); assert hasattr(Main,'toggle_quicklook'); assert hasattr(Main,'compare_panes'); assert hasattr(Main,'jump'); assert hasattr(Main,'toggle_focus'); assert hasattr(Main,'_sidebar_section'); assert hasattr(Main,'open_workspace_named'); assert hasattr(Main,'show_keybindings'); assert hasattr(Main,'quick_create'); assert hasattr(Main,'refresh_current'); assert hasattr(Main,'input_diagnostics'); assert hasattr(FilePane,'forward'); assert hasattr(Main,'clipboard_inspector'); assert hasattr(Main,'folder_health'); assert hasattr(Main,'duplicate_finder'); assert hasattr(Main,'saved_searches'); assert hasattr(Main,'manage_niru_actions'); assert hasattr(Main,'manage_recipes'); assert hasattr(Main,'run_niru_action'); assert hasattr(Main,'run_recipe'); assert hasattr(Main,'open_with'); assert hasattr(Main,'file_associations'); assert hasattr(Main,'context_lens'); assert hasattr(Main,'closeEvent'); assert hasattr(Main,'manage_clouds'); assert hasattr(Main,'open_cloud'); assert hasattr(Main,'close_split'); assert hasattr(SearchWorker,'cancel'); assert hasattr(Main,'all_actions'); assert hasattr(Main,'_save_work_basket'); assert hasattr(Main,'path_actions'); assert callable(safe_extract_zip); assert callable(safe_extract_tar); print('NIRUORG self-test OK'); return 0
 app=QApplication(sys.argv); app.setApplicationName(APP); app.setOrganizationName('NIRU'); app.setDesktopFileName('niruorg'); w=Main(sys.argv[1] if len(sys.argv)>1 else None); w.show(); w.startup_trace.mark('show called'); return app.exec()
if __name__=='__main__':raise SystemExit(main())
