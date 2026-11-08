#!/bin/bash
set -euo pipefail
replay_root=$(cd "$(dirname "$0")/.." && pwd)
actor_assets=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/new_data_20261105_v1/runtime_assets
monitor_assets=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/authorization_cpsc4880_20261105_879a8821d635/runtime_assets
dependencies=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/new_data_20261105_v1/python_dependencies
image="$monitor_assets/vllm_0.13.0.sif"
gpu=()
if [[ -n ${CUDA_VISIBLE_DEVICES:-} && -n ${SLURM_JOB_GPUS:-} ]]; then gpu=(--nv); fi
mkdir -p "$replay_root/runtime_cache/vllm" "$replay_root/runtime_cache/triton"
exec apptainer exec "${gpu[@]}" --cleanenv \
  --bind "$replay_root:$replay_root" --bind "$actor_assets:$actor_assets:ro" \
  --bind "$monitor_assets:$monitor_assets:ro" --bind "$dependencies:$dependencies:ro" --pwd "$replay_root" \
  --env "SLURM_JOB_ID=${SLURM_JOB_ID:-}" --env "SLURM_JOB_ACCOUNT=${SLURM_JOB_ACCOUNT:-}" \
  --env "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}" --env "TGF_ALLOCATION_START=${TGF_ALLOCATION_START:-}" \
  --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 --env HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  --env "TIKTOKEN_RS_CACHE_DIR=$actor_assets/harmony" --env "HF_HOME=$replay_root/runtime_cache/hf" \
  --env "VLLM_CACHE_ROOT=$replay_root/runtime_cache/vllm" --env "TRITON_CACHE_DIR=$replay_root/runtime_cache/triton" \
  --env TOKENIZERS_PARALLELISM=false --env OMP_NUM_THREADS=6 --env PYTHONUNBUFFERED=1 \
  --env VLLM_USE_TRITON_FLASH_ATTN=0 --env VLLM_DISABLE_SINKS=1 \
  "$image" /usr/bin/python3 "$replay_root/airline_dev_v1/cluster_bootstrap.py" "$@"
