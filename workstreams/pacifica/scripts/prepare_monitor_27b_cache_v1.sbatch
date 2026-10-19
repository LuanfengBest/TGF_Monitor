#!/bin/bash -l
#SBATCH --job-name=monitor-27b-cache
#SBATCH --partition=education
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/monitor_27b_cache-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
timeout --signal=TERM --kill-after=20s 1140s .venv/bin/python scripts/prepare_monitor_27b_cache_v1.py
