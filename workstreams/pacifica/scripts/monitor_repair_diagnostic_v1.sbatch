#!/bin/bash -l
#SBATCH --job-name=monitor-repair-diag
#SBATCH --partition=gpu
#SBATCH --gpus=a40:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=96G
#SBATCH --time=01:30:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/monitor_repair_diagnostic_v1-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONNOUSERSITE=1 TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export OMP_NUM_THREADS=4
timeout --signal=TERM --kill-after=20s 5320s runtime/tgf_sft_pilot_v1/venv/bin/python scripts/monitor_repair_diagnostic_runtime_v1.py run
