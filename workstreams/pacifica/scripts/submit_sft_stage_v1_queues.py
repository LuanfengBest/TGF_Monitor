"""Submit only the next gated stage; receipts prevent accidental repeated jobs."""
import argparse
from datetime import datetime
import json,subprocess
from pathlib import Path
import sft_three_arm_runtime_v1 as r

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('preflight','ordinary_sft','evidence_sft','evaluation'))
    stage=parser.parse_args().stage
    scheduler_path=r.ROOT/'configs/sft_scheduler_v1.json'
    scheduler=r.read(scheduler_path)
    for name,digest in scheduler['source_hashes'].items():assert r.sha(r.ROOT/name)==digest,name
    plan=r.read(r.PLAN)
    for name,digest in plan['source_hashes'].items():assert r.sha(r.ROOT/name)==digest,name
    r.data_gate()
    weights=r.read(r.WEIGHTS/'receipt.json')
    assert weights['status']=='all_22_files_verified_gpu_preflight_pending'
    if stage!='preflight':
        rec=r.read(r.RESULTS/'preflight/receipt.json')
        assert rec['status']=='passed' and rec['training_eligible'] is True
        assert rec['plan_sha256']==r.sha(r.PLAN)
    if stage in ('evidence_sft','evaluation'):
        # Sequential jobs make failure stopping explicit; no queued training after a failed arm.
        rec=r.read(r.RESULTS/'ordinary_sft/receipt.json');assert rec['status']=='completed'
    if stage=='evaluation':
        rec=r.read(r.RESULTS/'evidence_sft/receipt.json');assert rec['status']=='completed'
    q=subprocess.check_output(['squeue','-u','hpcllm_rz377','--noheader'],text=True,timeout=20)
    assert not q.strip(),'Inspect running jobs before next submission'
    assert not (r.RESULTS/stage).exists(),'Stage already reserved/attempted'
    path=r.ROOT/'results'/f'sft_three_arm_v1_{stage}_submission.json'
    record={'status':'submission_started','stage':stage,'submitted_at':datetime.now().astimezone().isoformat(),
            'plan_sha256':r.sha(r.PLAN),'queue_before':q,'scheduler_policy_sha256':r.sha(scheduler_path)}
    r.save(path,record)
    try:
        cp=subprocess.run(['sbatch','--parsable',f'scripts/sft_three_arm_v1_{stage}_queues.sbatch'],cwd=r.ROOT,text=True,capture_output=True,timeout=30)
        record.update(status='submitted' if cp.returncode==0 else 'failed',returncode=cp.returncode,stdout=cp.stdout,stderr=cp.stderr)
    except BaseException as exc:
        record.update(status='unknown_outcome_do_not_retry',error=repr(exc));raise
    finally:
        path.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
    assert record['returncode']==0
if __name__=='__main__':main()
