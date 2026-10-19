#!/bin/bash -l
#SBATCH --job-name=tgf-prospective-cpu
#SBATCH --partition=education
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:10:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/prospective_runtime_v2-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
timeout --signal=TERM --kill-after=15s 550s .venv/bin/python scripts/prospective_runtime_v2.py
