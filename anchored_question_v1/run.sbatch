#!/bin/bash
#SBATCH --job-name=anchored_question24
#SBATCH --account=cpsc4880
#SBATCH --partition=gpu_h200
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=h200:1
#SBATCH --cpus-per-task=6
#SBATCH --mem=160G
#SBATCH --time=02:00:00
#SBATCH --no-requeue
#SBATCH --output=logs/%x_%j.log
set -euo pipefail
export TGF_ALLOCATION_START=$(date +%s)
cd /nfs/roberts/project/cpsc4880/cpsc4880_rz377/anchored_question_20261106_v1
mkdir gpu_attempt
image=/nfs/roberts/project/cpsc4880/cpsc4880_rz377/authorization_cpsc4880_20261105_879a8821d635/runtime_assets/vllm_0.13.0.sif
python3 airline_dev_v1/verify_image.py "$image"
bash anchored_question_v1/cluster_python.sh -m anchored_question_v1.preflight \
  --bundle project/anchored_question_diagnostic_2026-11-06/bundle --output admission \
  --actor-snapshot /nfs/roberts/project/cpsc4880/cpsc4880_rz377/new_data_20261105_v1/runtime_assets/hf/models--openai--gpt-oss-120b/snapshots/b5c939de8f754692c1647ca79fbf85e8c1e70f8a \
  --monitor-snapshot /nfs/roberts/project/cpsc4880/cpsc4880_rz377/authorization_cpsc4880_20261105_879a8821d635/runtime_assets/hf/models--Qwen--Qwen3-32B/snapshots/9216db5781bf21249d130ec9da846c4624c16137 \
  --prior-assets airline_dev_v1/prior_assets.json --max-seconds 1800
bash anchored_question_v1/cluster_python.sh -m anchored_question_v1.campaign \
  --bundle project/anchored_question_diagnostic_2026-11-06/bundle \
  --preflight admission/preflight.json --permit permit.json --output comparison
