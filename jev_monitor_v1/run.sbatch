#!/bin/bash
#SBATCH --job-name=jev_qwen_2x2
#SBATCH --account=cpsc4880
#SBATCH --partition=gpu_h200
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=h200:1
#SBATCH --cpus-per-task=6
#SBATCH --mem=160G
#SBATCH --time=01:30:00
#SBATCH --no-requeue
#SBATCH --output=logs/%x_%j.log
set -euo pipefail
# Submit with --chdir to a dedicated transferred checkout; never run in an old campaign directory.
export JEV_ALLOCATION_START=$(date +%s)
mkdir allocation_once_jev_2x2
finish_allocation() {
  experiment_exit=$?
  export JEV_ALLOCATION_EXIT="$experiment_exit"
  python3 - <<'PY'
import json,os,time,pathlib
p=pathlib.Path('project/jev_monitor_2x2_2026-11-11/results/allocation_finished.json')
p.parent.mkdir(parents=True,exist_ok=True)
with p.open('x') as f:
 json.dump({'job_id':os.environ.get('SLURM_JOB_ID'),'allocation_wall_seconds':time.time()-float(os.environ['JEV_ALLOCATION_START']), 'gpus':1, 'exit_code':int(os.environ['JEV_ALLOCATION_EXIT']), 'scheduler_sacct_verification':'pending collection'},f)
PY
}
trap finish_allocation EXIT
bash jev_monitor_v1/cluster_python.sh
