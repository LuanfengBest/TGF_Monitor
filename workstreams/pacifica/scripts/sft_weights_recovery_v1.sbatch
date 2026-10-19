#!/bin/bash -l
#SBATCH --job-name=sft-weights-recovery-v1
#SBATCH --partition=education
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/sft_weights_recovery_v1-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
python scripts/sft_weights_recovery_v1.py
