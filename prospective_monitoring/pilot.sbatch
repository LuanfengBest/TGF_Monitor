#!/bin/bash -l
#SBATCH --job-name=tgf_prospective_dev
#SBATCH --partition=gpu_h200
#SBATCH --account=hpcllm
#SBATCH --qos=normal
#SBATCH --gpus=h200:1
#SBATCH --mem=160G
#SBATCH --cpus-per-task=8
#SBATCH --time=04:00:00
#SBATCH --no-requeue
#SBATCH --output=logs/%x_%j.log
set -euo pipefail
: "${TGF_REPO:?Set the deployed repository}"
: "${TGF_PYTHON:?Set the pinned Python executable or wrapper}"
: "${TGF_CONFIG:?Set the frozen prospective pilot config}"
: "${TGF_TASKS:?Set the frozen new-development task manifest}"
: "${TGF_PREFLIGHT:?Set the fresh prospective preflight receipt}"
: "${TGF_PERMIT:?Set the new-development authorization receipt}"
: "${TGF_RUN:?Set a new, nonexisting output directory}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false
export VLLM_USE_TRITON_FLASH_ATTN=0
export VLLM_DISABLE_SINKS=1
unset VLLM_ATTENTION_BACKEND
cd "$TGF_REPO"
exec "$TGF_PYTHON" -m prospective_monitoring.campaign --config "$TGF_CONFIG" --tasks "$TGF_TASKS" --preflight "$TGF_PREFLIGHT" --permit "$TGF_PERMIT" --run "$TGF_RUN"
