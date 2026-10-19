"""Single bounded read-only qualification using already installed dependencies."""
import hashlib,importlib.metadata,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 start=time.monotonic();target=ROOT/'results/prospective_actor_v5_preflight.json'
 with target.open('x') as f:json.dump({'status':'started'},f)
 r={'status':'failed','preflight_script_sha256':sha(Path(__file__)),'plan_sha256':sha(ROOT/'configs/prospective_actor_v5.json'),'checks':[],
    'dependency_job':'29560911','new_installations':0,'new_cpu_jobs':0,'model_calls':0,'gpu_jobs':0}
 try:
  old=json.loads((ROOT/'results/prospective_runtime_v2_receipt.json').read_text())
  assert old['status']=='failed' and old['checks'][0]['returncode']==old['checks'][1]['returncode']==0
  versions={d.metadata['Name'].lower().replace('_','-'):d.version for d in importlib.metadata.distributions(path=[str(ROOT/'runtime/prospective_actor_v2_deps')])}
  assert versions==old['versions']
  r['versions']=versions
  for args in [['scripts/prospective_actor_v5.py','verify'],['-m','unittest','discover','-s','tests','-p','test_prospective_actor_v5.py','-q'],['-m','unittest','discover','-s','tests','-p','test_audit_bank_alias_v3.py','-q']]:
   proc=subprocess.run([sys.executable,*args],cwd=ROOT,timeout=max(1,110-(time.monotonic()-start)))
   r['checks'].append({'args':args,'returncode':proc.returncode});proc.check_returncode()
  r['status']='passed'
 except BaseException as exc:r['error']=repr(exc);raise
 finally:
  r['elapsed_seconds']=time.monotonic()-start;target.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
if __name__=='__main__':main()
