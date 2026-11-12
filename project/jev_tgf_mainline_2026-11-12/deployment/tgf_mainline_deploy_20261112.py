"""One-use cluster preparation, bounded submission, status and verified export."""
import argparse,hashlib,json,os,subprocess,time,zipfile
from pathlib import Path
NAME='tgf_jev_mainline_20261112_v1'
BASE=Path('/nfs/roberts/project/cpsc4880/cpsc4880_rz377')
ROOT=BASE/NAME
BUNDLE=ROOT/'project/jev_tgf_mainline_2026-11-12'
OUT=BUNDLE/'results'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def call(argv):
 r=subprocess.run(argv,capture_output=True,text=True,timeout=60)
 if r.returncode:raise RuntimeError(json.dumps({'argv':argv,'code':r.returncode,'stdout':r.stdout,'stderr':r.stderr}))
 return r.stdout.strip()
def check(seal):
 assert sha(BUNDLE/'manifest.json')==seal
 for name,h in read(BUNDLE/'manifest.json')['files'].items():assert sha(ROOT/name)==h,name
 s=read(OUT/'jev_smoke.json');assert s['valid']==8 and s['manifest_sha256']==seal
 for rid,h in s['result_hashes'].items():assert sha(OUT/'judgments'/'jev'/rid/'result.json')==h

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','cpu','actor','qwen','status','export']);p.add_argument('--archive-sha');p.add_argument('--seal',required=True);a=p.parse_args()
 assert os.environ['USER']=='cpsc4880_rz377'
 if a.action=='prepare':
  archive=Path.home()/(NAME+'.zip');assert sha(archive)==a.archive_sha
  ROOT.mkdir(exist_ok=False)
  with zipfile.ZipFile(archive) as z:
   for info in z.infolist():
    name=Path(info.filename);assert not name.is_absolute() and '..' not in name.parts and name.parts[0]==NAME
    target=ROOT.joinpath(*name.parts[1:]);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as f:f.write(z.read(info))
  check(a.seal);(ROOT/'logs').mkdir()
  queue=call(['squeue','-h','-u',os.environ['USER']]);assert not queue,'Existing work needs inspection'
  assoc=call(['sacctmgr','-nP','show','assoc','where','user='+os.environ['USER'],'format=User,Account,Partition,QOS']);assert 'cpsc4880_rz377|cpsc4880|' in assoc and 'normal' in assoc
  tests={stage:call(['sbatch','--test-only','--chdir='+str(ROOT),str(ROOT/'tgf_jev_mainline_v1'/f'{stage}.sbatch')]) for stage in ('cpu','actor','qwen')}
  save(ROOT/'deployment_admission.json',{'seal':a.seal,'archive_sha256':a.archive_sha,'queue':queue,'associations':assoc,'scheduler_dry_runs':tests,'submitted_jobs':0});print('DEPLOYMENT_ADMITTED',flush=True);return
 check(a.seal)
 if a.action in ('cpu','actor','qwen'):
  stage=a.action
  if stage!='cpu':
   assert read(OUT/'admission.json')['ready']
   jid=read(ROOT/'submissions/cpu.json')['job_id'];state=call(['sacct','-nP','-j',jid,'--format=JobID,State,ExitCode'])
   assert jid+'|COMPLETED|0:0' in state
  if stage=='qwen':
   assert read(OUT/'actor_summary.json')['complete']
   jid=read(ROOT/'submissions/actor.json')['job_id'];state=call(['sacct','-nP','-j',jid,'--format=JobID,State,ExitCode'])
   assert jid+'|COMPLETED|0:0' in state
  queue=call(['squeue','-h','-u',os.environ['USER']]);assert not queue,'Inspect current queue before any allocation'
  save(ROOT/'submissions'/f'{stage}.claim.json',{'seal':a.seal,'created_unix':time.time(),'attempt':1})
  response=call(['sbatch','--parsable','--chdir='+str(ROOT),str(ROOT/'tgf_jev_mainline_v1'/f'{stage}.sbatch')]);job=response.split(';')[0];assert job.isdigit()
  receipt={'stage':stage,'job_id':job,'manifest_sha256':a.seal,'submitted_unix':time.time()};save(ROOT/'submissions'/f'{stage}.json',receipt);print(json.dumps(receipt),flush=True);return
 if a.action=='status':
  subs=[read(x) for x in sorted((ROOT/'submissions').glob('*.json')) if not x.name.endswith('.claim.json')]
  for s in subs:
   jid=s['job_id'];print(json.dumps({'stage':s['stage'],'job_id':jid,'accounting':call(['sacct','-nP','-j',jid,'--format=JobID,State,ExitCode,ElapsedRaw,Start,End,AllocTRES'])}))
  for name in ('admission.json','actor_summary.json','qwen_summary.json'):
   f=OUT/name
   if f.exists():
    d=read(f);print(json.dumps({name:{k:v for k,v in d.items() if k not in ('assets','rows')}}))
  print(json.dumps({'collected':len(list((OUT/'collection').glob('*/result_private.json'))),'followup_results':len(list((OUT/'followups').glob('*/result.json'))),'reviews':len(list((OUT/'reviews').glob('*/result.json'))),'qwen_results':len(list((OUT/'judgments/qwen').glob('*/result.json')))}))
  if subs:
   logs=sorted((ROOT/'logs').glob('*.log'),key=lambda x:x.stat().st_mtime)
   if logs:print(logs[-1].read_text(errors='replace')[-1500:])
  return
 # This archive contains only experiment inputs and outputs, never runtime assets or credentials.
 files=[p for p in OUT.rglob('*') if p.is_file()]+list((ROOT/'submissions').glob('*.json'))+list((ROOT/'logs').glob('*.log'))
 manifest={str(f.relative_to(ROOT)):sha(f) for f in files}
 archive=Path.home()/(NAME+'_results.zip')
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
  for f in files:z.write(f,str(f.relative_to(ROOT)))
  z.writestr('RESULT_FILES.json',json.dumps(manifest,sort_keys=True))
 print(json.dumps({'archive':str(archive),'sha256':sha(archive),'files':len(files),'bytes':archive.stat().st_size}),flush=True)
if __name__=='__main__':main()
