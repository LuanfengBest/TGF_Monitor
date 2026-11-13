#!/bin/bash
#SBATCH --job-name=agv-qwen
#SBATCH --account=cpsc4880
#SBATCH --partition=gpu_h200
#SBATCH --gpus=h200:1
#SBATCH --cpus-per-task=6
#SBATCH --mem=160G
#SBATCH --time=00:40:00
#SBATCH --no-requeue
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?submit from repository root}"
: "${1:?pass an existing output directory outside the repo}"
dest=$(cd "$1" && pwd)
assets=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/authorization_cpsc4880_20261105_879a8821d635/runtime_assets
deps=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/new_data_20261105_v1/python_dependencies
mkdir -p "$dest/cache"
exec apptainer exec --nv --cleanenv --pwd "$PWD" \
  --bind "$PWD:$PWD:ro,$assets:$assets:ro,$deps:$deps:ro,$dest:/agv-output" \
  --env "PYTHONPATH=$PWD:$deps" --env "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}" \
  --env "SLURM_JOB_ID=$SLURM_JOB_ID" --env "SLURM_JOB_ACCOUNT=$SLURM_JOB_ACCOUNT" \
  --env HF_HUB_OFFLINE=1 --env HF_HOME=/agv-output/cache/hf \
  --env VLLM_CACHE_ROOT=/agv-output/cache/vllm --env TRITON_CACHE_DIR=/agv-output/cache/triton \
  --env VLLM_DISABLE_SINKS=1 --env VLLM_USE_TRITON_FLASH_ATTN=0 \
  "$assets/vllm_0.13.0.sif" /usr/bin/python3 -B -m agv_v0.run \
  --judge qwen --limit "${2:-1}" --live-output /agv-output/qwen.jsonl
