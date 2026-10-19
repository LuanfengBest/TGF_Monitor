"""Verify then submit once; unknown submission outcomes must never be retried."""
import datetime,json,subprocess
import initial_review_ablation_v1 as p
def main():
 p.verify(p.read(p.PLAN))
 assert not (p.ROOT/'results/initial_review_ablation_v1.reservation.json').exists()
 q=subprocess.check_output(['squeue','-u','hpcllm_rz377','--noheader'],text=True,timeout=20)
 if q.strip():raise ValueError('Existing queue requires inspection')
 cp=subprocess.run([str(p.ROOT/'.venv/bin/python'),'-m','unittest','discover','-s','tests','-p','test_initial_review_ablation_v1.py','-q'],cwd=p.ROOT,text=True,capture_output=True,timeout=60)
 if cp.returncode:raise ValueError(cp.stdout+cp.stderr)
 r={'status':'submission_started','submitted_at':datetime.datetime.now().astimezone().isoformat(),'plan_sha256':p.sha(p.PLAN),'queue_before':q,'test_stdout':cp.stdout,'test_stderr':cp.stderr,'gpu_seconds_limit':900,'max_calls':6}
 path=p.ROOT/'results/initial_review_ablation_v1_submission.json';p.create(path,r)
 try:
  submitted=subprocess.run(['sbatch','--parsable','scripts/initial_review_ablation_v1.sbatch'],cwd=p.ROOT,text=True,capture_output=True,timeout=30)
  r.update(status='submitted' if submitted.returncode==0 else 'failed',returncode=submitted.returncode,stdout=submitted.stdout,stderr=submitted.stderr)
 except BaseException as exc:r.update(status='unknown_outcome_do_not_retry',error=repr(exc));raise
 finally:path.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
 if r['returncode']:raise RuntimeError('Submission failed; do not retry')
if __name__=='__main__':main()
