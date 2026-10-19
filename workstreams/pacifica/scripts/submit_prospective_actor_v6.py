"""Submit the frozen stage at most once after successful remote qualification."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=ROOT/'configs/prospective_actor_v6.json';h=hashlib.sha256(p.read_bytes()).hexdigest()
 pre=json.loads((ROOT/'results/prospective_actor_v6_preflight.json').read_text())
 assert pre['status']=='passed' and pre['plan_sha256']==h
 assert not (ROOT/'results/prospective_actor_v6.reservation.json').exists()
 q=subprocess.check_output(['squeue','-u','hpcllm_rz377','--noheader'],text=True,timeout=20)
 if q.strip():raise ValueError('Existing queue entries require inspection before submitting')
 r={'status':'submission_started','submitted_at':datetime.datetime.now().astimezone().isoformat(),'queue_before':q,'plan_sha256':h,'gpu_seconds_limit':2100,'actor_call_limit':240}
 target=ROOT/'results/prospective_actor_v6_submission.json'
 with target.open('x') as f:json.dump(r,f,indent=2)
 try:
  cp=subprocess.run(['sbatch','--parsable','scripts/prospective_actor_v6.sbatch'],cwd=ROOT,text=True,capture_output=True,timeout=30)
  r.update(returncode=cp.returncode,stdout=cp.stdout,stderr=cp.stderr,status='submitted' if cp.returncode==0 else 'failed')
 except BaseException as e:r.update(status='unknown_outcome_do_not_retry',error=repr(e));raise
 finally:target.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
 if r['returncode']!=0:raise RuntimeError('Submission failed; receipt retained')
if __name__=='__main__':main()
