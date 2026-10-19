"""Qualify locally on the cluster and submit this bounded batch at most once."""
import datetime,json,subprocess
import prospective_four_arm_v2 as p
def main():
 plan=p.verify(p.read(p.PLAN))
 assert not (p.ROOT/'results/prospective_four_arm_v2.reservation.json').exists()
 q=subprocess.check_output(['squeue','-u','hpcllm_rz377','--noheader'],text=True,timeout=20)
 if q.strip():raise ValueError('Existing queue requires inspection')
 checks=[]
 for pattern in ('test_prospective_four_arm_v2.py','test_public_event_contract_v2.py'):
  cp=subprocess.run([str(p.ROOT/'.venv/bin/python'),'-m','unittest','discover','-s','tests','-p',pattern,'-q'],cwd=p.ROOT,text=True,capture_output=True,timeout=60)
  checks.append({'pattern':pattern,'returncode':cp.returncode,'stdout':cp.stdout,'stderr':cp.stderr})
  if cp.returncode:raise ValueError(cp.stdout+cp.stderr)
 r={'status':'submission_started','submitted_at':datetime.datetime.now().astimezone().isoformat(),'plan_sha256':p.sha(p.PLAN),'queue_before':q,'checks':checks,'gpu_seconds_limit':plan['gpu_seconds'],'max_calls':plan['max_calls']}
 path=p.ROOT/'results/prospective_four_arm_v2_submission.json';p.create(path,r)
 try:
  submitted=subprocess.run(['sbatch','--parsable','scripts/prospective_four_arm_v2.sbatch'],cwd=p.ROOT,text=True,capture_output=True,timeout=30)
  r.update(status='submitted' if submitted.returncode==0 else 'failed',returncode=submitted.returncode,stdout=submitted.stdout,stderr=submitted.stderr)
 except BaseException as exc:r.update(status='unknown_outcome_do_not_retry',error=repr(exc));raise
 finally:path.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
 if r['returncode']:raise RuntimeError('Submission failed; do not retry')
if __name__=='__main__':main()
