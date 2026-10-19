#!/bin/bash -l
#SBATCH --job-name=tgf-pair-first
#SBATCH --partition=gpu_devel
#SBATCH --gpus=rtx_5000_ada:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:15:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/paired_first-%j.log
set -euo pipefail
shopt -s expand_aliases
module load ollama/0.22.0-GCCcore-13.3.0-CUDA-12.8.0
module load Python/3.12.3-GCCcore-13.3.0
export OLLAMA_MODELS=/nfs/roberts/scratch/hpcllm/hpcllm_rz377/tgf_ollama_models
export OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_CONTEXT_LENGTH=32768
trap 'ollama-down || true' EXIT
ollama serve
date -Is
hostname
timeout --signal=TERM --kill-after=20s 840s .venv/bin/python scripts/run_paired_v1.py --stage first --output "results/paired_first_${SLURM_JOB_ID}"
.venv/bin/python scripts/verify_paired_v1.py --output "results/paired_first_${SLURM_JOB_ID}"
date -Is
