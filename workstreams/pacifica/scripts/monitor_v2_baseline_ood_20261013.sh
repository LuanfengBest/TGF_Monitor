#!/bin/bash -l
#SBATCH --job-name=newfam-base-v1
#SBATCH --partition=gpu_devel
#SBATCH --gpus=rtx_5000_ada:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:20:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/monitor_v2_baseline-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
cd /nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
python - <<'PY'
from pathlib import Path
import json, hashlib, os, datetime
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha('configs/monitor_v2_baseline_v1.json') == '9444b9a6433f436b98b1ed716948876625e8edf3b6c85f3fee816740a623e9bd'
assert sha('scripts/monitor_v2_baseline_v1.sbatch') == '463bb0297eb9d03e756f285a37a6dbea22cd6794eceeeeb4d491dc752c5cd076'
pre = json.loads(Path('results/monitor_v2_upload_receipt_20261013.json').read_text())
assert pre['status'] == 'completed' and len(pre['checks']) == 5
assert all(c['returncode'] == 0 for c in pre['checks'])
assert not Path('results/monitor_v2_baseline_v1.reservation.json').exists()
r = {'recorded_at': datetime.datetime.now().astimezone().isoformat(), 'job_id': os.environ['SLURM_JOB_ID'],
     'interface': 'Open OnDemand Project Manager', 'project_id': 'vjd0pem5',
     'command': 'bash -l scripts/monitor_v2_baseline_v1.sbatch',
     'plan_sha256': sha('configs/monitor_v2_baseline_v1.json'),
     'preflight_receipt_sha256': sha('results/monitor_v2_upload_receipt_20261013.json'),
     'max_calls': 11, 'gpu_walltime_seconds': 1200, 'training_runs': 0}
with Path('results/monitor_v2_baseline_v1_submission.json').open('x') as f:
    f.write(json.dumps(r, indent=2)+'\n')
PY
bash -l scripts/monitor_v2_baseline_v1.sbatch
