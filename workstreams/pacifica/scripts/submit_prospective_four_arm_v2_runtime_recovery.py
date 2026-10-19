"""Only after human approval: verify immutable delivery and submit one recovery."""
import datetime,json,subprocess
import prospective_four_arm_v2_runtime_recovery as r

def main():
 manifest=r.base.read(r.base.ROOT/'configs/prospective_four_arm_v2_runtime_recovery_delivery.json')
 assert manifest['policy']==r.POLICY
 for name,sha in manifest['source_hashes'].items():assert r.base.sha(r.base.ROOT/name)==sha,name
 r.verify();r.approved()
 assert not r.RESERVATION.exists()
 receipt=r.base.ROOT/'results/prospective_four_arm_v2_runtime_recovery_submission.json'
 assert not receipt.exists()
 q=subprocess.check_output(['squeue','-u','hpcllm_rz377','--noheader'],text=True,timeout=20)
 if q.strip():raise ValueError('Existing jobs require inspection')
 checks=[]
 for pattern in ('test_prospective_four_arm_v2_runtime_recovery.py','test_prospective_four_arm_v2.py','test_public_event_contract_v2.py'):
  cp=subprocess.run([str(r.base.ROOT/'.venv/bin/python'),'-m','unittest','discover','-s','tests','-p',pattern,'-q'],cwd=r.base.ROOT,text=True,capture_output=True,timeout=60)
  checks.append({'pattern':pattern,'returncode':cp.returncode,'stdout':cp.stdout,'stderr':cp.stderr})
  if cp.returncode:raise ValueError(cp.stdout+cp.stderr)
 record={'status':'submission_started','submitted_at':datetime.datetime.now().astimezone().isoformat(),'policy':r.POLICY,'queue_before':q,'checks':checks,'decision_sha256':r.base.sha(r.DECISION)}
 r.base.create(receipt,record)
 try:
  cp=subprocess.run(['sbatch','--parsable','scripts/prospective_four_arm_v2_runtime_recovery.sbatch'],cwd=r.base.ROOT,text=True,capture_output=True,timeout=30)
  record.update(status='submitted' if cp.returncode==0 else 'failed',returncode=cp.returncode,stdout=cp.stdout,stderr=cp.stderr)
 except BaseException as exc:record.update(status='unknown_outcome_do_not_retry',error=repr(exc));raise
 finally:receipt.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
 if record['returncode']:raise RuntimeError('Submission failed; do not retry')
if __name__=='__main__':main()
