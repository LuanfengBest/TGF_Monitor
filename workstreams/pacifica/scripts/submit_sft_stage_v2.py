"""Submit one approved, gated stage; never retry an existing reservation."""
import argparse
from datetime import datetime
import json
import subprocess
import sft_three_arm_runtime_v2 as r


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('ordinary_sft', 'evidence_sft', 'evaluation'))
    stage = parser.parse_args().stage
    plan = r.read(r.PLAN)
    for name, digest in plan['source_hashes'].items():
        assert r.sha(r.ROOT / name) == digest, name
    r.data_gate()
    r.qualification_gate()
    assert plan['remaining_gpu_seconds_max'] == 21600
    assert plan['training_seconds_each'] == 4500 and plan['evaluation_seconds'] == 12600
    # The failed v1 preflight is the sole previous GPU attempt; no old effect run may exist.
    for old_stage in ('ordinary_sft', 'evidence_sft', 'evaluation'):
        assert not (r.ROOT / 'results/sft_three_arm_v1' / old_stage).exists()
        assert not (r.ROOT / 'results' / f'sft_three_arm_v1_{old_stage}_submission.json').exists()
    required = []
    if stage in ('evidence_sft', 'evaluation'):
        required.append('ordinary_sft')
    if stage == 'evaluation':
        required.append('evidence_sft')
    for previous in required:
        receipt = r.read(r.RESULTS / previous / 'receipt.json')
        assert receipt['status'] == 'completed' and receipt['epochs'] == 2
        assert receipt['plan_sha256'] == r.sha(r.PLAN)
        assert receipt['data_manifest_sha256'] == r.sha(r.DATA / 'manifest.json')
    queue = subprocess.check_output(['squeue', '-u', 'hpcllm_rz377', '--noheader'], text=True, timeout=20)
    assert not queue.strip(), 'Inspect active jobs before submission'
    assert not (r.RESULTS / stage).exists(), 'Stage already attempted'
    path = r.ROOT / 'results' / f'sft_three_arm_v2_{stage}_submission.json'
    record = {'status': 'submission_started', 'stage': stage,
              'submitted_at': datetime.now().astimezone().isoformat(),
              'plan_sha256': r.sha(r.PLAN), 'queue_before': queue,
              'qualification_sha256': r.sha(r.ROOT / 'analysis/sft_technical_qualification_v2.json'),
              'approval_sha256': r.sha(r.ROOT / 'results/sft_runtime_budget_approval_20261014.json')}
    r.save(path, record)
    try:
        cp = subprocess.run(['sbatch', '--parsable', f'scripts/sft_three_arm_v2_{stage}.sbatch'],
                            cwd=r.ROOT, text=True, capture_output=True, timeout=30)
        record.update(status='submitted' if cp.returncode == 0 else 'failed',
                      returncode=cp.returncode, stdout=cp.stdout, stderr=cp.stderr)
    except BaseException as exc:
        record.update(status='unknown_outcome_do_not_retry', error=repr(exc))
        raise
    finally:
        path.write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps(record), flush=True)
    assert record['returncode'] == 0


if __name__ == '__main__':
    main()
