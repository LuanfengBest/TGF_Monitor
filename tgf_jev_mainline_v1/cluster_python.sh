#!/bin/bash
set -euo pipefail
experiment_root=$(cd "$(dirname "$0")/.." && pwd)
monitor_assets=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/authorization_cpsc4880_20261105_879a8821d635/runtime_assets
actor_assets=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/new_data_20261105_v1/runtime_assets
python_dependencies=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/new_data_20261105_v1/python_dependencies
gpu=()
if [[ -n ${SLURM_JOB_GPUS:-} ]]; then gpu=(--nv); fi
mkdir -p "$experiment_root/runtime_cache/vllm" "$experiment_root/runtime_cache/triton"
exec apptainer exec "${gpu[@]}" --cleanenv \
 --bind "$experiment_root:$experiment_root" --bind "$monitor_assets:$monitor_assets:ro" \
 --bind "$actor_assets:$actor_assets:ro" --bind "$python_dependencies:$python_dependencies:ro" --pwd "$experiment_root" \
 --env "PYTHONPATH=$experiment_root:$python_dependencies" --env "TIKTOKEN_RS_CACHE_DIR=$actor_assets/harmony" \
 --env "SLURM_JOB_ID=${SLURM_JOB_ID:-}" --env "SLURM_JOB_ACCOUNT=${SLURM_JOB_ACCOUNT:-}" \
 --env "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}" --env "TGF_MAINLINE_START=${TGF_MAINLINE_START:-}" \
 --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 --env HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
 --env "HF_HOME=$experiment_root/runtime_cache/hf" --env "VLLM_CACHE_ROOT=$experiment_root/runtime_cache/vllm" \
 --env "TRITON_CACHE_DIR=$experiment_root/runtime_cache/triton" --env TOKENIZERS_PARALLELISM=false \
 --env OMP_NUM_THREADS=6 --env PYTHONUNBUFFERED=1 --env VLLM_USE_TRITON_FLASH_ATTN=0 --env VLLM_DISABLE_SINKS=1 \
 "$monitor_assets/vllm_0.13.0.sif" /usr/bin/python3 "$@"
