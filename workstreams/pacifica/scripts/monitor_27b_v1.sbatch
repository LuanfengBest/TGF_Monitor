#!/bin/bash -l
#SBATCH --job-name=monitor-27b-v1
#SBATCH --partition=gpu_devel
#SBATCH --gpus=rtx_5000_ada:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:30:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/monitor_27b_v1-%j.log
set -euo pipefail
module purge
module load Python/3.12.3-GCCcore-13.3.0
timeout --signal=TERM --kill-after=25s 1740s .venv/bin/python scripts/serve_monitor_27b_v1.py
