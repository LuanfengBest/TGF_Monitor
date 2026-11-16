#!/bin/bash
#SBATCH --job-name=tgf_matched_v1
#SBATCH --partition=gpu_h200
#SBATCH --gpus=h200:1
#SBATCH --mem=160G
#SBATCH --cpus-per-task=8
#SBATCH --time=01:00:00
#SBATCH --output=logs/%x_%j.log
set -euo pipefail
export TGF_ALLOCATION_START="$(date +%s)"
: "${TGF_REPO:?Set the absolute repository path}"
: "${TGF_PYTHON:?Set the Python executable from the pinned environment}"
: "${TGF_PREFLIGHT:?Set the passed CPU preflight receipt path}"
: "${TGF_RUN:?Set a new, nonexisting output directory}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false
export VLLM_USE_TRITON_FLASH_ATTN=0
export VLLM_DISABLE_SINKS=1
unset VLLM_ATTENTION_BACKEND
cd "$TGF_REPO"
exec "$TGF_PYTHON" -m matched_followup.runner run --preflight "$TGF_PREFLIGHT" --run "$TGF_RUN"
