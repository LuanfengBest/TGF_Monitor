#!/bin/bash -l
#SBATCH --job-name=monitor-select-v1
#SBATCH --partition=gpu_devel
#SBATCH --gpus=rtx_5000_ada:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:10:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/monitor_selection-%j.log
set -euo pipefail
shopt -s expand_aliases
module load ollama/0.22.0-GCCcore-13.3.0-CUDA-12.8.0
module load Python/3.12.3-GCCcore-13.3.0
export OLLAMA_MODELS=/nfs/roberts/scratch/hpcllm/hpcllm_rz377/tgf_ollama_models
export OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_CONTEXT_LENGTH=32768
trap 'ollama-down || true' EXIT
ollama serve
if [ "$1" = smoke ]; then
  timeout --signal=TERM --kill-after=20s 540s .venv/bin/python scripts/monitor_selection_v1.py run --stage smoke --output "results/monitor_selection_smoke_${SLURM_JOB_ID}"
else
  test "$1" = remaining
  test "$#" -eq 2
  timeout --signal=TERM --kill-after=20s 2040s .venv/bin/python scripts/monitor_selection_v1.py run --stage remaining --prefix "$2" --output "results/monitor_selection_remaining_${SLURM_JOB_ID}"
fi
