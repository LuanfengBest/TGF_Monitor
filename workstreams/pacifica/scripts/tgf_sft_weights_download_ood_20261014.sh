#!/bin/bash -l
#SBATCH --job-name=tgf-sft-weights-v1
#SBATCH --partition=education
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/tgf_sft_weights_v1-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
python runtime/tgf_sft_weights_delivery_v1/tgf_sft_weights_download_v1.py
