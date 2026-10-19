#!/bin/bash -l
#SBATCH --job-name=tgf-prospective-v1
#SBATCH --partition=gpu_devel
#SBATCH --gpus=rtx_5000_ada:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:35:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/prospective_actor_v1-%j.log
set -euo pipefail
shopt -s expand_aliases
module load ollama/0.22.0-GCCcore-13.3.0-CUDA-12.8.0
module load Python/3.12.3-GCCcore-13.3.0
export OLLAMA_MODELS=/nfs/roberts/scratch/hpcllm/hpcllm_rz377/tgf_ollama_models
export OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_CONTEXT_LENGTH=131072
trap 'ollama-down || true' EXIT
.venv/bin/python scripts/prospective_actor_v1.py verify
ollama serve
timeout --signal=TERM --kill-after=15s 2000s .venv/bin/python scripts/prospective_actor_v1.py run --output "results/prospective_actor_v1_${SLURM_JOB_ID}"
