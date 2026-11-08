#!/bin/bash
set -euo pipefail
diagnostic_root=$(cd "$(dirname "$0")/.." && pwd)
actor_assets=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/new_data_20261105_v1/runtime_assets
monitor_assets=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/authorization_cpsc4880_20261105_879a8821d635/runtime_assets
dependencies=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/new_data_20261105_v1/python_dependencies
image="$monitor_assets/vllm_0.13.0.sif"
gpu=()
if [[ -n ${CUDA_VISIBLE_DEVICES:-} && -n ${SLURM_JOB_GPUS:-} ]]; then gpu=(--nv); fi
mkdir -p "$diagnostic_root/runtime_cache/vllm" "$diagnostic_root/runtime_cache/triton"
exec apptainer exec "${gpu[@]}" --cleanenv \
  --bind "$diagnostic_root:$diagnostic_root" --bind "$actor_assets:$actor_assets:ro" \
  --bind "$monitor_assets:$monitor_assets:ro" --bind "$dependencies:$dependencies:ro" --pwd "$diagnostic_root" \
  --env "SLURM_JOB_ID=${SLURM_JOB_ID:-}" --env "SLURM_JOB_ACCOUNT=${SLURM_JOB_ACCOUNT:-}" \
  --env "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}" --env "TGF_ALLOCATION_START=${TGF_ALLOCATION_START:-}" \
  --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 --env HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  --env "TIKTOKEN_RS_CACHE_DIR=$actor_assets/harmony" --env "HF_HOME=$diagnostic_root/runtime_cache/hf" \
  --env "VLLM_CACHE_ROOT=$diagnostic_root/runtime_cache/vllm" --env "TRITON_CACHE_DIR=$diagnostic_root/runtime_cache/triton" \
  --env TOKENIZERS_PARALLELISM=false --env OMP_NUM_THREADS=6 --env PYTHONUNBUFFERED=1 \
  --env VLLM_USE_TRITON_FLASH_ATTN=0 --env VLLM_DISABLE_SINKS=1 \
  "$image" /usr/bin/python3 "$diagnostic_root/evidence_use_v2/cluster_bootstrap.py" "$@"
