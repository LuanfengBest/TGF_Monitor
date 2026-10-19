#!/bin/bash -l
#SBATCH --job-name=monitor-runtime-v1
#SBATCH --partition=education
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:15:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/monitor_runtime_v1-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
timeout --signal=TERM --kill-after=20s 840s .venv/bin/python scripts/prepare_monitor_runtime_v1.py
