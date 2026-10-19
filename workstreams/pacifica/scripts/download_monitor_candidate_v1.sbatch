#!/bin/bash -l
#SBATCH --job-name=monitor-candidate-download
#SBATCH --partition=education
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/monitor_candidate_download-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
export OLLAMA_MODELS=/nfs/roberts/scratch/hpcllm/hpcllm_rz377/tgf_ollama_models
timeout --signal=TERM --kill-after=20s 1140s .venv/bin/python scripts/download_monitor_candidate_v1.py
