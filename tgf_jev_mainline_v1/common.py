"""Durable artifacts and a new, independent execution envelope."""
import hashlib,json,os,time
from pathlib import Path
from jev_monitor_v1.core import canonical,digest,strict_json
ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'project/jev_tgf_mainline_2026-11-12'
OUT=BUNDLE/'results'

def read(p): return strict_json(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
 return h.hexdigest()
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:
  f.write(canonical(v)+'\n');f.flush();os.fsync(f.fileno())
def verify():
 m=read(BUNDLE/'manifest.json')
 for name,h in m['files'].items():
  if sha(ROOT/name)!=h: raise ValueError('Frozen file differs: '+name)
 return sha(BUNDLE/'manifest.json')
def cfg(): return read(BUNDLE/'config.json')
def tasks(): return read(BUNDLE/'tasks_PRIVATE.json')['tasks']
def checkpoint(directory,name):
 directory=Path(directory)
 files={str(p.relative_to(directory)):sha(p) for p in sorted(directory.rglob('*')) if p.is_file() and p.name!=name}
 save(directory/name,{'files':files,'created_unix':time.time(),'manifest_sha256':verify()})
def verify_checkpoint(directory,name):
 d=read(Path(directory)/name)
 if d['manifest_sha256']!=verify(): raise ValueError('Seal belongs to another experiment')
 for p,h in d['files'].items():
  if sha(Path(directory)/p)!=h: raise ValueError('Generated artifact differs: '+p)
 return d

def admission(which):
 seal=verify();a=read(OUT/'admission.json')
 smoke=read(OUT/'jev_smoke.json')
 if smoke.get('valid')!=8 or smoke['manifest_sha256']!=seal:raise ValueError('Jev interface not admitted')
 for rid,h in smoke['result_hashes'].items():
  if sha(OUT/'judgments'/'jev'/rid/'result.json')!=h:raise ValueError('Jev smoke artifact changed')
 if a['manifest_sha256']!=seal or not a['ready']: raise ValueError('No current CPU admission')
 for row in a['assets']:
  p=Path(row['path']);s=p.stat()
  if s.st_size!=row['bytes'] or s.st_mtime_ns!=row['mtime_ns'] or str(p.resolve())!=row['resolved']:
   raise ValueError('Asset changed after hash verification: '+str(p))
 if os.environ.get('SLURM_JOB_ACCOUNT')!='cpsc4880' or not os.environ.get('SLURM_JOB_ID'):
  raise ValueError('Requires checked cpsc4880 scheduler allocation')
 return seal
