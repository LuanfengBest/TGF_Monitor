#!/bin/bash
set -euo pipefail
experiment_root=$(cd "$(dirname "$0")/.." && pwd)
monitor_assets=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/authorization_cpsc4880_20261105_879a8821d635/runtime_assets
python_dependencies=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/new_data_20261105_v1/python_dependencies
image="$monitor_assets/vllm_0.13.0.sif"
exec apptainer exec --nv --cleanenv \
  --bind "$experiment_root:$experiment_root" --bind "$monitor_assets:$monitor_assets:ro" \
  --bind "$python_dependencies:$python_dependencies:ro" --pwd "$experiment_root" \
  --env "PYTHONPATH=$experiment_root/authorization_timing_recovery_v1/guard_bootstrap:$experiment_root:$python_dependencies" \
  --env "SLURM_JOB_ID=${SLURM_JOB_ID:-}" --env "SLURM_JOB_ACCOUNT=${SLURM_JOB_ACCOUNT:-}" \
  --env "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}" --env "TIMING_ALLOCATION_START=${TIMING_ALLOCATION_START:-}" \
  --env HF_HUB_OFFLINE=1 --env TRANSFORMERS_OFFLINE=1 --env HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  --env "HF_HOME=$experiment_root/runtime_cache/hf" --env "VLLM_CACHE_ROOT=$experiment_root/runtime_cache/vllm" \
  --env "TRITON_CACHE_DIR=$experiment_root/runtime_cache/triton" --env TOKENIZERS_PARALLELISM=false \
  --env OMP_NUM_THREADS=6 --env PYTHONUNBUFFERED=1 --env VLLM_USE_TRITON_FLASH_ATTN=0 --env VLLM_DISABLE_SINKS=1 \
  --env TIMING_REQUIRE_WARM_CACHE=1 \
  "$image" /usr/bin/python3 -B -m authorization_timing_recovery_v1.run --model qwen
