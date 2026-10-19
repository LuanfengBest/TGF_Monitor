#!/bin/bash -l
#SBATCH --job-name=travel-monitor-v1
#SBATCH --partition=gpu_devel
#SBATCH --gpus=rtx_5000_ada:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:15:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/travel_monitor_baseline-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
cd /nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
python - <<'PYCODE'
from pathlib import Path
import json,hashlib,os,datetime
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha('configs/travel_monitor_baseline_v1.json') == 'd0cb072b647ce86569f50a13f4fa7ebab56085c6e98fa2d6236549abb6febe04'
assert sha('scripts/travel_monitor_baseline_v1.sbatch') == '63233a72dd2aad8ab4646b09dcf9850ddcd5f760336cf51531f4ad3b4609cf31'
pre=json.loads(Path('results/travel_monitor_preflight_receipt_20261014.json').read_text())
assert pre['status']=='completed' and pre['plan_sha256']==sha('configs/travel_monitor_baseline_v1.json')
assert len(pre['checks'])==6 and all(x['returncode']==0 for x in pre['checks'])
assert not Path('results/travel_monitor_baseline_v1.reservation.json').exists()
r={'recorded_at':datetime.datetime.now().astimezone().isoformat(),'job_id':os.environ['SLURM_JOB_ID'],
 'interface':'Open OnDemand Project Manager','project_id':'vjd0pem5',
 'plan_sha256':sha('configs/travel_monitor_baseline_v1.json'),
 'preflight_receipt_sha256':sha('results/travel_monitor_preflight_receipt_20261014.json'),
 'max_calls':6,'gpu_walltime_seconds':900,'training_runs':0}
with Path('results/travel_monitor_submission_20261014.json').open('x') as f:
 f.write(json.dumps(r,indent=2)+'\n');f.flush();os.fsync(f.fileno())
PYCODE
bash -l scripts/travel_monitor_baseline_v1.sbatch
