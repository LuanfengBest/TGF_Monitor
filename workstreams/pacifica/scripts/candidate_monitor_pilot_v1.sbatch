#!/bin/bash -l
#SBATCH --job-name=candidate-monitor-v1
#SBATCH --partition=gpu_devel
#SBATCH --gpus=rtx_5000_ada:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=01:00:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/candidate_monitor-%j.log
set -euo pipefail
shopt -s expand_aliases
module load ollama/0.22.0-GCCcore-13.3.0-CUDA-12.8.0
module load Python/3.12.3-GCCcore-13.3.0
export OLLAMA_MODELS=/nfs/roberts/scratch/hpcllm/hpcllm_rz377/tgf_ollama_models
export OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_CONTEXT_LENGTH=32768
export TGF_MONITOR_OUT="results/candidate_monitor_pilot_v1_${SLURM_JOB_ID}"
cleanup() {
 local task_exit=$?
 trap - EXIT
 ollama-down || true
 .venv/bin/python - "$task_exit" <<'PY'
import datetime,json,os,sys
from pathlib import Path
p=Path(os.environ['TGF_MONITOR_OUT']);p.mkdir(parents=True,exist_ok=True)
(p/'lifecycle.json').write_text(json.dumps({'ended_at':datetime.datetime.now().astimezone().isoformat(),'exit_code':int(sys.argv[1]),'cleanup_requested':True,'job_id':os.environ.get('SLURM_JOB_ID')},indent=2)+'\n')
PY
 exit "$task_exit"
}
trap cleanup EXIT
.venv/bin/python scripts/candidate_monitor_pilot_v1.py verify
ollama serve
timeout --signal=TERM --kill-after=20s 3520s .venv/bin/python scripts/candidate_monitor_pilot_v1.py run --output "$TGF_MONITOR_OUT"
