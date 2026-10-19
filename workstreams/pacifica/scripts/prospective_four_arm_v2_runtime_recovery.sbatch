#!/bin/bash -l
#SBATCH --job-name=tgf-v2-runtime-recovery
#SBATCH --partition=gpu_devel
#SBATCH --gpus=rtx_5000_ada:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:42:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/prospective_four_arm_v2_runtime_recovery-%j.log
set -euo pipefail
shopt -s expand_aliases
module load ollama/0.22.0-GCCcore-13.3.0-CUDA-12.8.0
module load Python/3.12.3-GCCcore-13.3.0
export OLLAMA_MODELS=/nfs/roberts/scratch/hpcllm/hpcllm_rz377/tgf_ollama_models
export OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_CONTEXT_LENGTH=32768
trap 'ollama-down || true' EXIT
.venv/bin/python scripts/prospective_four_arm_v2_runtime_recovery.py verify
ollama serve
timeout --signal=TERM --kill-after=15s 2420s .venv/bin/python scripts/prospective_four_arm_v2_runtime_recovery.py run --output "results/prospective_four_arm_v2_runtime_recovery_${SLURM_JOB_ID}"
