"""Hash-gated, reservation-before-submit CPU recovery; never resubmit."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
def main():
    plan=json.loads((ROOT/'configs/sft_weights_recovery_v1.json').read_text())
    for name,digest in plan['source_hashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    assert not (ROOT/'runtime/sft_weights_recovery_v1').exists()
    q=subprocess.check_output(['squeue','-u','hpcllm_rz377','--noheader'],text=True,timeout=20)
    assert not q.strip(),'Inspect existing jobs before submitting'
    receipt=ROOT/'results/sft_weights_recovery_v1_submission.json'
    record={'status':'submission_started','started_at':datetime.now().astimezone().isoformat(),
            'plan_sha256':hashlib.sha256((ROOT/'configs/sft_weights_recovery_v1.json').read_bytes()).hexdigest(),'queue_before':q}
    with receipt.open('x') as f:json.dump(record,f,indent=2)
    try:
        cp=subprocess.run(['sbatch','--parsable','scripts/sft_weights_recovery_v1.sbatch'],cwd=ROOT,text=True,capture_output=True,timeout=30)
        record.update(status='submitted' if cp.returncode==0 else 'failed',returncode=cp.returncode,stdout=cp.stdout,stderr=cp.stderr)
    except BaseException as e:
        record.update(status='unknown_outcome_do_not_retry',error=repr(e));raise
    finally:
        receipt.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
    assert record['returncode']==0
if __name__=='__main__':main()
