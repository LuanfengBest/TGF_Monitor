#!/bin/bash -l
#SBATCH --job-name=sft-v1-ordinary_sft
#SBATCH --partition=gpu_devel
#SBATCH --gpus=a40:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=00:45:00
#SBATCH --chdir=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf
#SBATCH --output=/nfs/roberts/project/hpcllm/hpcllm_rz377/monitorability_tgf/logs/sft_three_arm_v1_ordinary_sft-%j.log
set -euo pipefail
module load Python/3.12.3-GCCcore-13.3.0
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONNOUSERSITE=1 TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export OMP_NUM_THREADS=4
timeout --signal=TERM --kill-after=20s 2630s runtime/tgf_sft_pilot_v1/venv/bin/python scripts/sft_three_arm_runtime_v1.py ordinary_sft
